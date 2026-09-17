"""Offline check of decimate.py against a synthetic interleaved bitstream. Run: python pi/test_decimate.py"""
import os,sys,tempfile,wave
import numpy as np
sys.path.insert(0,os.path.dirname(__file__));import decimate

def dsm2(x):
    """Plain 2nd-order delta-sigma, enough to make a realistic noise-shaped 1-bit stream."""
    i1=i2=0.;out=np.empty(len(x),dtype=np.uint8)
    for n,v in enumerate(x):
        y=1. if i2>=0 else -1.;out[n]=y>0;i1+=v-y;i2+=i1-y
    return out

def amplitude(x,f,fs=48000):
    t=np.arange(len(x))/fs;return 2*abs(np.mean(x*np.exp(-2j*np.pi*f*t)))

secs=0.5;n=int(decimate.FS_MOD*secs);t=np.arange(n)/decimate.FS_MOD
left=dsm2(0.5*np.sin(2*np.pi*1000*t));right=dsm2(0.25*np.sin(2*np.pi*18000*t)+0.1)
bits=np.empty(2*n,dtype=np.uint8);bits[0::2]=left;bits[1::2]=right          # wire order: L,R,L,R…
words=np.packbits(bits[:len(bits)//64*64]).view('>u4').astype('<u4')           # MSB first into left word, then right word
with tempfile.TemporaryDirectory() as d:
    raw,out=os.path.join(d,'c.raw'),os.path.join(d,'c.wav');words.tofile(raw)
    decimate.main([raw,out,'--keep-dc'])
    with wave.open(out) as w:pcm=np.frombuffer(w.readframes(w.getnframes()),dtype='<i4').reshape(-1,2)/2**31
x=pcm[2000:-2000];x=x[:len(x)//48*48]   # skip filter settling; whole periods of 1 kHz
aL,aR,dc=amplitude(x[:,0],1000),amplitude(x[:,1],18000),x[:,1].mean()
print(f'left 1 kHz amplitude {aL:.4f} (want 0.5000); right 18 kHz amplitude {aR:.4f} (want 0.2500, {20*np.log10(aR/0.25):+.2f} dB); right DC {dc:+.4f} (want +0.1000)')
print(f'crosstalk: 18 kHz in left {20*np.log10(amplitude(x[:,0],18000)/0.25+1e-12):.0f} dB, 1 kHz in right {20*np.log10(amplitude(x[:,1],1000)/0.5+1e-12):.0f} dB')
assert abs(aL-0.5)<0.005 and abs(20*np.log10(aR/0.25))<0.3 and abs(dc-0.1)<0.005,'decimator response out of tolerance'
print('PASS')
