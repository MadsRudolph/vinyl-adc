#!/usr/bin/env python3
"""Turn a raw Vinyl ADC I2S capture into a 48 kHz stereo WAV. Needs only NumPy.

Capture on the Pi (the ADC is the clock master, 64 BCLK per 48 kHz frame):

    arecord -D hw:CARD=vinyladc -c 2 -r 48000 -f S32_LE -t raw capture.raw

Each 32-bit word is NOT a PCM sample. The digital board interleaves the two
1-bit modulator outputs on the data line: one bit per BCLK, left when MCLK is
high, right when it is low. A 64-bit frame therefore carries 32 left and 32
right modulator bits at 1.536 MHz each. This script de-interleaves them and
decimates by 32: a 4th-order CIC (÷8, to 192 kHz) followed by a 161-tap FIR
(÷4) that also flattens the CIC droop to 20 kHz.
"""
import argparse,sys,wave
import numpy as np

CIC_ORDER,CIC_R,FIR_R,FIR_TAPS,FS_MOD=4,8,4,161,1_536_000

class Cic:
    """Hogenauer CIC decimator with state, so a long capture can be streamed in chunks. int64 wrap-around is harmless here."""
    def __init__(self,order=CIC_ORDER,ratio=CIC_R):
        self.order,self.ratio=order,ratio;self.integ=[np.int64(0)]*order;self.comb=[np.int64(0)]*order;self.count=0
    def process(self,x):
        y=x.astype(np.int64)
        with np.errstate(over='ignore'):
            for k in range(self.order):
                y=np.cumsum(y,dtype=np.int64)+self.integ[k];self.integ[k]=y[-1]
            first=(self.ratio-1-self.count)%self.ratio;self.count=(self.count+len(y))%self.ratio
            y=y[first::self.ratio]
            for k in range(self.order):
                prev=self.comb[k];self.comb[k]=y[-1] if len(y) else prev
                y=np.diff(np.concatenate(([prev],y)))
        return y/float(self.ratio**self.order)

def compensating_fir(taps=FIR_TAPS,fs=FS_MOD/CIC_R,passband=20_000.,stopband=28_000.):
    """Windowed frequency-sampling low-pass whose passband is the inverse of the CIC droop. Aliases of 28 kHz+ fold above 20 kHz."""
    grid=1<<14;f=np.linspace(0,fs/2,grid+1)
    with np.errstate(divide='ignore',invalid='ignore'):
        cic=np.abs(np.sin(np.pi*f*CIC_R/FS_MOD)/(CIC_R*np.sin(np.pi*f/FS_MOD)))**CIC_ORDER
    cic[0]=1.
    want=np.where(f<=passband,1/cic,0.);edge=(f>passband)&(f<stopband)
    want[edge]=(1/cic[edge])*0.5*(1+np.cos(np.pi*(f[edge]-passband)/(stopband-passband)))
    h=np.fft.irfft(want,2*grid);h=np.roll(h,taps//2)[:taps]*np.kaiser(taps,10.)
    return h/h.sum()

class FirDecimator:
    def __init__(self,h,ratio=FIR_R):self.h,self.ratio=h,ratio;self.tail=np.zeros(len(h)-1);self.count=0
    def process(self,x):
        buf=np.concatenate((self.tail,x));self.tail=buf[-(len(self.h)-1):]
        y=np.convolve(buf,self.h,mode='valid');first=(-self.count)%self.ratio;self.count=(self.count+len(y))%self.ratio
        return y[first::self.ratio]

def frames_from(path):
    """Yield (n,2) uint32 arrays of I2S words from a raw S32_LE stereo file or a 32-bit stereo WAV."""
    with open(path,'rb') as f:
        if f.read(4)==b'RIFF':
            f.close()
            with wave.open(path,'rb') as w:
                if (w.getnchannels(),w.getsampwidth())!=(2,4):sys.exit('WAV must be 2 channels of 32-bit PCM')
                while True:
                    raw=w.readframes(48000)
                    if not raw:return
                    yield np.frombuffer(raw,dtype='<u4').reshape(-1,2)
        f.seek(0)
        while True:
            raw=f.read(48000*8);raw=raw[:len(raw)//8*8]
            if not raw:return
            yield np.frombuffer(raw,dtype='<u4').reshape(-1,2)

def split_bits(words):
    """Frame = left word then right word, each MSB first, in the order the bits arrived on the wire."""
    bits=np.unpackbits(words.astype('>u4').view(np.uint8)).reshape(len(words),64)
    return bits[:,0::2].reshape(-1),bits[:,1::2].reshape(-1)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('capture');p.add_argument('output',nargs='?',default='capture.wav')
    p.add_argument('--swap',action='store_true',help='exchange left and right if a signal fed into the LEFT input shows up on the right')
    p.add_argument('--keep-dc',action='store_true',help='keep the DC offset instead of removing each channel\'s mean')
    p.add_argument('--gain-db',type=float,default=0.,help='gain applied before writing; 0 dB maps modulator full scale to digital full scale')
    a=p.parse_args(argv)
    h=compensating_fir();chains=[(Cic(),FirDecimator(h)) for _ in range(2)];out=[[],[]];ones=[0,0];total=0
    for words in frames_from(a.capture):
        streams=split_bits(words);total+=streams[0].size
        for ch,bits in enumerate(streams):
            ones[ch]+=int(bits.sum());cic,fir=chains[ch];out[ch].append(fir.process(cic.process(bits.astype(np.int8)*2-1)))
    if not total:sys.exit('No complete frames in the capture')
    audio=np.vstack([np.concatenate(c) for c in out])
    if a.swap:audio=audio[::-1]
    names=('right','left') if a.swap else ('left','right')
    print(f'{total/FS_MOD:.2f} s captured, {audio.shape[1]} output samples at 48 kHz')
    for ch in (0,1):
        density=ones[ch]/total;where=names[ch]
        flag='  <- stuck bitstream: check that channel board, its J21 shunt and the bus' if density<.02 or density>.98 else ''
        print(f'  bitstream {ch} -> {where:5s}: one-density {density:.4f} (0.5 = zero input){flag}')
    dc=audio.mean(axis=1)
    if not a.keep_dc:audio=audio-dc[:,None]
    audio=audio*10**(a.gain_db/20)
    for ch,name in enumerate(('left','right')):
        x=audio[ch];rms=np.sqrt(np.mean(x**2));peak=np.max(np.abs(x))
        print(f'  {name:5s}: DC {dc[ch]:+.4f} FS, RMS {20*np.log10(max(rms,1e-12)):+.1f} dBFS, peak {20*np.log10(max(peak,1e-12)):+.1f} dBFS')
    pcm=np.clip(np.round(audio.T*(2**31-1)),-2**31,2**31-1).astype('<i4')
    with wave.open(a.output,'wb') as w:w.setnchannels(2);w.setsampwidth(4);w.setframerate(48000);w.writeframes(pcm.tobytes())
    print('wrote',a.output)
if __name__=='__main__':main()
