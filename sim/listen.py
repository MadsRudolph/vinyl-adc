#!/usr/bin/env python3
"""Hear what the Vinyl ADC would do to a signal. NumPy only (ffmpeg needed for non-WAV input).

    python sim/listen.py                      # built-in plucked-string clip
    python sim/listen.py song.flac --start 30 --seconds 15

The audio is interpolated to the 1.536 MHz modulator clock, run through the continuous-time model of
the real loop (sim/modulator.py with the E96 parts from sim/components.py: 3 MHz op-amps, 200 ns loop
delay, resonator, ELD path), and the resulting 1-bit streams are decimated by the very filter the Pi
uses (pi/decimate.py). Analog noise is added at the level measured on the bench on 17 September 2026
(flat -125 dBFS/Hz in band). Outputs land in sim/listen-out/:

    original.wav        the input, 48 kHz, peak-normalised to the chosen level
    adc.wav             the same clip after the ADC model and the decimator
    residual+40dB.wav   adc minus the time-aligned original, limited to 20 Hz-20 kHz and boosted 40 dB:
                        the audible part of what the ADC adds
"""
import argparse,subprocess,sys,time,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'sim'),str(ROOT/'pi')]
import modulator as M,components as C,decimate as D

FS_OUT=48000;OSR=32;WARM=512;XFADE=64   # output samples of lead-in and crossfade per slice

def build():
    c=C.coeffs_from(C.synthesise())
    return M.Modulator(c['a'],k=c['k'],g=c['g'],k0=c['k0'],gbw=3e6/C.FS,delay=C.DELAY)

def run_batched(mod,u):
    """u: (streams, samples) in units of modulator full scale. Identical maths to Modulator.run, vectorised over streams."""
    A,B=mod._ss();Ad1,Bd1=M._discretise(A,B,mod.delay);Ad2,Bd2=M._discretise(A,B,1-mod.delay);o=mod._out_index()
    F=(Ad2@Ad1).T;Gu=(Ad2@Bd1[:,0]+Bd2[:,0]);Gp=Ad2@Bd1[:,1];Gv=Bd2[:,1]
    x=np.zeros((u.shape[0],A.shape[0]));vp=np.ones(u.shape[0]);out=np.empty(u.shape,dtype=np.int8)
    for i in range(u.shape[1]):
        v=np.where(x[:,o]+mod.k0*vp>0,1.,-1.)
        x=x@F+np.outer(u[:,i],Gu)+np.outer(vp,Gp)+np.outer(v,Gv)
        out[:,i]=v;vp=v
    return out

def simulate(mod,x_hi,slices=256):
    """Modulate and decimate one long input. Returns 48 kHz audio.

    The loop is chaotic, so independently simulated bit slices cannot be spliced: every seam would break the
    noise shaping. Instead each slice (with a warm-up lead-in for the loop and the filters) is decimated on
    its own, and the slices are crossfaded as audio, where a seam is only one noise realisation handing
    over to the next.
    """
    n_out=len(x_hi)//OSR;seg=-(-n_out//slices);span=(WARM+seg+XFADE)*OSR
    pad=np.concatenate((np.zeros(WARM*OSR),x_hi,np.zeros(span+seg*slices*OSR-len(x_hi)))).astype(np.float32)
    bits=run_batched(mod,np.stack([pad[k*seg*OSR:k*seg*OSR+span] for k in range(slices)]))
    h=D.compensating_fir();y=np.zeros(seg*slices+XFADE);ramp=np.linspace(0,1,XFADE,endpoint=False)
    for k in range(slices):
        a=D.FirDecimator(h).process(D.Cic().process(bits[k]))[WARM:WARM+seg+XFADE].copy()
        if k:a[:XFADE]*=ramp
        if k<slices-1:a[seg:]*=1-ramp
        y[k*seg:k*seg+seg+XFADE]+=a
    return y[:n_out],float(np.mean(bits[:,WARM*OSR:]>0))

def upsample(x):
    """48 kHz -> 192 kHz by spectral zero-padding, then linear x8 to 1.536 MHz (its images sit far outside the band)."""
    n=len(x);X=np.fft.rfft(x);Y=np.zeros(2*n+1,dtype=complex);Y[:len(X)]=X;y=np.fft.irfft(Y,4*n)*4
    t=np.arange(n*OSR)/8.;return np.interp(t,np.arange(len(y)),y)

def pluck(f,dur,rng,decay=.996):
    N=int(round(FS_OUT/f));buf=rng.uniform(-1,1,N);buf=np.convolve(buf-buf.mean(),np.ones(3)/3,'same');out=np.empty(int(dur*FS_OUT));n=0
    while n<len(out):
        m=min(N,len(out)-n);out[n:n+m]=buf[:m];buf=decay*.5*(buf+np.roll(buf,1));n+=N
    return out

def demo_clip():
    """Arpeggiated plucked strings over a bass note, Am-F-C-G, ending in a long decay so the noise floor is audible."""
    rng=np.random.default_rng(7);beat=.3;note=lambda m:440*2**((m-69)/12);out=np.zeros((2,int(13*FS_OUT)))
    chords=[(45,[57,60,64,69]),(41,[53,57,60,65]),(48,[55,60,64,67]),(43,[55,59,62,67])]*2;t=0.
    for bass,tones in chords:
        for ch in (0,1):
            b=pluck(note(bass),2.6,rng,.9985)*.5;i=int(t*FS_OUT);out[ch,i:i+len(b)]+=b[:out.shape[1]-i]
        for j,mnote in enumerate(tones+tones[::-1]):
            p=pluck(note(mnote),1.8,rng)*.45;pan=.25+.5*(j%2);i=int((t+j*beat/2*1.25)*FS_OUT)
            out[0,i:i+len(p)]+=(1-pan)*p[:out.shape[1]-i];out[1,i:i+len(p)]+=pan*p[:out.shape[1]-i]
        t+=1.5
    fade=np.ones(out.shape[1]);k=int(1.5*FS_OUT);fade[-k:]=np.linspace(1,0,k)**2;return out*fade

def load(path,start,seconds):
    cmd=['ffmpeg','-v','error','-ss',str(start),'-t',str(seconds),'-i',path,'-f','f32le','-ac','2','-ar',str(FS_OUT),'-']
    raw=subprocess.run(cmd,capture_output=True,check=True).stdout;return np.frombuffer(raw,dtype='<f4').reshape(-1,2).T.astype(float)

def write_wav(path,x):
    pcm=np.clip(np.round(x.T*(2**23-1)),-2**23,2**23-1).astype('<i4');b=pcm.reshape(-1,1).view(np.uint8).reshape(-1,4)[:,:3]
    with wave.open(str(path),'wb') as w:w.setnchannels(x.shape[0]);w.setsampwidth(3);w.setframerate(FS_OUT);w.writeframes(b.tobytes())

def align(ref,y):
    """Least-squares gain and (fractional) delay of y against ref, applied to ref in the frequency domain."""
    n=min(len(ref),len(y));ref,y=ref[:n],y[:n];R,Y=np.fft.rfft(ref),np.fft.rfft(y);f=np.fft.rfftfreq(n,1/FS_OUT)
    lag=int(np.argmax(np.fft.irfft(Y*np.conj(R)))) ;lag=lag-n if lag>n//2 else lag
    band=(f>100)&(f<8000);Xs=Y*np.conj(R)*np.exp(2j*np.pi*f*lag/FS_OUT);w=np.abs(Xs)*band
    slope=np.sum(w*f*np.angle(Xs))/np.sum(w*f*f);tau=lag/FS_OUT-slope/(2*np.pi)
    shifted=np.fft.irfft(R*np.exp(-2j*np.pi*f*tau),n);g=float(shifted@y/(shifted@shifted));return g*shifted,tau,g

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('input',nargs='?');p.add_argument('--start',type=float,default=0.);p.add_argument('--seconds',type=float,default=15.)
    p.add_argument('--peak-dbfs',type=float,default=-6.,help='input peak relative to modulator full scale (the loop overloads a few dB below 0)')
    p.add_argument('--noise-dbfs-hz',type=float,default=-125.,help='analog noise density added at the input; -125 matches the bench, -200 disables it')
    p.add_argument('--out',default=str(ROOT/'sim/listen-out'));a=p.parse_args()
    x=load(a.input,a.start,a.seconds) if a.input else demo_clip()
    x=x/np.abs(x).max()*10**(a.peak_dbfs/20);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);mod=build();rng=np.random.default_rng(1)
    print(f'{x.shape[1]/FS_OUT:.1f} s stereo, peak {a.peak_dbfs:+.1f} dBFS; modulator: a={np.round(mod.a,3)}, g={mod.g:.3f}, k0={mod.k0:.3f}, delay {mod.delay:.2f} Ts')
    sigma=np.sqrt(10**(a.noise_dbfs_hz/10)*C.FS/2);adc=[];t0=time.time()
    for ch,name in enumerate(('left','right')):
        hi=upsample(x[ch]);y,density=simulate(mod,hi+rng.normal(0,sigma,len(hi)));adc.append(y)
        print(f'  {name}: {len(hi)/1e6:.1f} M modulator clocks, one-density {density:.4f}, {time.time()-t0:.0f} s elapsed')
    n=min(map(len,adc));adc=np.vstack([y[:n] for y in adc]);ref=np.zeros_like(adc);skip=2000
    for ch in (0,1):
        ref[ch],tau,g=align(x[ch],adc[ch]);res=(adc[ch]-ref[ch])[skip:-skip];sig=ref[ch][skip:-skip]
        R=np.abs(np.fft.rfft(res*np.hanning(len(res))))**2;f=np.fft.rfftfreq(len(res),1/FS_OUT);inb=R[(f>=20)&(f<=20000)].sum()/R.sum()
        print(f"  {('left','right')[ch]}: chain delay {tau*1e3:.3f} ms, gain {20*np.log10(g):+.3f} dB; residual {20*np.log10(res.std()):.1f} dBFS = {20*np.log10(sig.std()/res.std()):.1f} dB below the music ({100*inb:.0f}% of it inside 20 Hz-20 kHz)")
    res=adc-ref;F=np.fft.rfft(res,axis=1);f=np.fft.rfftfreq(res.shape[1],1/FS_OUT);F[:,(f<20)|(f>20000)]=0;audible=np.fft.irfft(F,res.shape[1],axis=1)
    print(f'  audible part of the residual (20 Hz-20 kHz): {20*np.log10(audible[:,2000:-2000].std()):.1f} dBFS; the rest is shaped noise between 20 and 24 kHz that the decimator lets through')
    write_wav(out/'original.wav',ref);write_wav(out/'adc.wav',adc);write_wav(out/'residual+40dB.wav',np.clip(audible*100,-1,1))
    print('wrote',out/'original.wav',',',out/'adc.wav','and',out/'residual+40dB.wav')
if __name__=='__main__':main()
