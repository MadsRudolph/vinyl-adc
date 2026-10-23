"""Synthesised sound effects for the short (no samples, nothing to license), and the music cut.

    .venv/bin/python sfx.py
"""
import subprocess
from pathlib import Path
import numpy as np,soundfile as sf

HERE=Path(__file__).resolve().parent;OUT=HERE/'public/audio';OUT.mkdir(parents=True,exist_ok=True)
SR=48000;rng=np.random.default_rng(7)

def save(name,y,peak=.9):
    y=y/np.max(np.abs(y))*peak;sf.write(OUT/f'{name}.wav',np.c_[y,y].astype(np.float32),SR)

def env(n,a,d):
    t=np.arange(n)/SR;return np.minimum(1,t/a)*np.exp(-t/d)

def bandnoise(n,lo,hi):
    X=np.fft.rfft(rng.standard_normal(n));f=np.fft.rfftfreq(n,1/SR);X[(f<lo)|(f>hi)]=0;return np.fft.irfft(X,n)

def sweep_noise(dur,f0,f1,q=.35):
    """Noise through a band that glides from f0 to f1: a whoosh."""
    n=int(dur*SR);x=rng.standard_normal(n);out=np.zeros(n);hop=512;win=np.hanning(2048)
    for i in range(0,n-2048,hop):
        u=i/n;fc=f0*(f1/f0)**u;seg=np.fft.rfft(x[i:i+2048]*win);f=np.fft.rfftfreq(2048,1/SR)
        seg*=np.exp(-.5*(np.log(np.maximum(f,1)/fc)/q)**2);out[i:i+2048]+=np.fft.irfft(seg,2048)
    t=np.linspace(0,1,n);return out*np.sin(np.pi*t)**1.5

# impact: a sub drop plus a noise crack
n=int(1.6*SR);t=np.arange(n)/SR
sub=np.sin(2*np.pi*(55*t+ (90-55)*.06*(1-np.exp(-t/.06))))*env(n,.002,.45)
crack=bandnoise(n,800,9000)*env(n,.001,.05)
save('impact',1.0*sub+.35*crack)
# whoosh up and down
save('whoosh',sweep_noise(.7,300,6000),.7)
save('whoosh_down',sweep_noise(.8,5000,250),.7)
# tick (counter) and click (UI)
n=int(.05*SR);t=np.arange(n)/SR
save('tick',np.sin(2*np.pi*2400*t)*env(n,.0005,.008),.35)
save('click',(np.sin(2*np.pi*1200*t)+.5*bandnoise(n,2000,8000))*env(n,.0003,.006),.5)
# glitch: bit-crushed square bursts
n=int(.45*SR);t=np.arange(n)/SR;g=np.sign(np.sin(2*np.pi*(180+900*rng.random())*t))
g*=(rng.random(n//1200+1).repeat(1200)[:n]>.35);g=np.round(g*4)/4
save('glitch',g*env(n,.001,.25),.45)
# vinyl: needle drop thump + crackle bed
n=int(4*SR);t=np.arange(n)/SR;cr=np.zeros(n);idx=rng.integers(0,n,900);cr[idx]=rng.standard_normal(900)*rng.random(900)**3
cr=np.convolve(cr,np.exp(-np.arange(60)/8),'same');hiss=bandnoise(n,2000,12000)*.02
thump=np.sin(2*np.pi*70*t)*env(n,.002,.07)
save('needle',thump*.9+cr*.6+hiss,.6)
# riser into the drop
n=int(2.0*SR);t=np.arange(n)/SR;r=sweep_noise(2.0,200,9000,.5)*np.linspace(0,1,n)**2
save('riser',r,.6)

# music: Voxel Revolution from 61.9 s, so its drop (78.2 s) lands on "So PCBWay built it properly" (16.3 s)
src=HERE/'audio/Voxel_Revolution.mp3'
import json
vo=json.load(open(HERE/'public/vo.json'));drop=[l for l in vo['lines'] if l['key']=='pcbway'][0]['start']
subprocess.run(['ffmpeg','-v','error','-y','-ss',f'{78.2-drop:.3f}','-t','46','-i',str(src),'-ar','48000','-ac','2',str(OUT/'music.wav')],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(HERE/'audio/vo.wav'),'-af','highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=4,loudnorm=I=-16:TP=-1.5:LRA=7','-ar','48000','-ac','2',str(OUT/'vo.wav')],check=True)
print('ok')
