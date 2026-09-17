"""Synthetic fixtures for exercising scripts without any device. Never hardware evidence."""
import numpy as np

class SimulatedAD3:
    def __init__(self,fault=None):self.fault=fault;self.w1=None;self.info={'serial':'SIMULATED','name':'Synthetic fixture','sdk':'none'};self.cleanup_errors=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def wave(self,kind,frequency=0.,amplitude=0.,offset=0.):self.w1=(kind,float(frequency),float(amplitude),float(offset),None)
    def wave_custom(self,frequency,shape,amplitude):self.w1=('custom',float(frequency),float(amplitude),0.,np.asarray(shape,dtype=float))
    def wave_off(self):self.w1=None
    def supply_3v3(self,*args):pass
    def supply_status(self):return 3.3,0.012
    def scope_fixture(self,kind,rate,count):
        t=np.arange(count)/rate;rng=np.random.default_rng(19)
        sine=lambda amp:amp*np.sin(2*np.pi*1000*t)
        square=lambda f,v:v*((t*f)%1<.5)
        if kind=='pump-check':a,b=square(192000,5),np.zeros(count)
        elif kind=='rails-power' or kind=='rails-channel':a,b=np.full(count,5.),np.full(count,-4.1)
        elif kind=='rails-digital':a,b=np.full(count,5.),np.full(count,3.3)
        elif kind=='references':a,b=np.full(count,2.5),np.full(count,-2.5)
        elif kind=='pi-clocks':a,b=square(3072000/(2 if self.fault=='wrong-clock' else 1),3.3),square(48000,3.3)
        elif kind=='bus-clocks':a,b=square(1536000/(2 if self.fault=='wrong-clock' else 1),5),square(192000,5)
        elif kind in ('q-left','q-right'):
            bits=np.repeat(rng.integers(0,2,count//32+1),32)[:count]
            a,b=(np.zeros(count) if self.fault=='stuck-channel' else 5.*bits),square(1536000,5)
        elif kind=='pi-data':
            bits=rng.integers(0,2,count);bits=np.repeat(bits[:count//16],16)[:count] if count>=16 else bits
            a,b=(np.zeros(count) if self.fault=='stuck-channel' else 3.3*bits),square(3072000,3.3)
        elif kind.startswith('mux-'):
            ql,qr=map(int,kind[-2:]);bits=np.where((t*1536000)%1<.5,ql,qr);a,b=5.*bits,3.3*bits
        elif kind.startswith('tone-'):a,b=sine(float(kind[5:])),np.full(count,5.)
        else:raise ValueError(kind)
        if self.fault=='bad-rail' and kind.startswith('rails'):a=np.full(count,3.2)
        return np.array([a,b])+rng.normal(0,.001,(2,count)),rate
    def logic_fixture(self,kind,rate,duration=None):
        n=round(rate*duration) if duration else 32768;t=np.arange(n)/rate
        clk=lambda f:((t*f)%1<.5).astype(np.uint16)
        words=np.zeros(n,dtype=np.uint16)
        if kind.startswith(('clocks','mux')):
            frequencies={0:6144000,1:1536000,2:3072000,3:48000,4:3072000,5:48000,10:192000}
            if self.fault=='wrong-clock':frequencies[1]/=2
            for ch,f in frequencies.items():words|=clk(f)<<ch
            ql,qr=map(int,kind[-2:]) if kind.startswith('mux') else (0,0)
            words|=np.uint16(ql<<7|qr<<8)
            dout=np.where(clk(1536000),ql,qr).astype(np.uint16)
            if self.fault=='swapped-mux':dout=1-dout
            words|=(dout<<6)|(dout<<9)
        else:
            cycles=np.floor(t*1536000).astype(int);ct=np.arange(cycles[-1]+1)/1536000
            amp=float(kind[5:])*.25 if kind.startswith('tone-') else 0
            if self.fault=='missing-tone':amp=0
            density=.5+amp*np.sin(2*np.pi*1000*ct)
            acc=np.cumsum(density);q=(np.floor(acc)-np.floor(np.r_[0,acc[:-1]])).astype(np.uint16)[cycles]
            if self.fault=='stuck-channel':q=np.zeros_like(q)
            words=clk(1536000)|(q<<1)|((1-q)<<2)|(q<<3)|((1-q)<<4)|(q<<5)
        return words,rate

class SimulatedPi:
    """Stands in for the Pi's /api/audio: renders what the ADC model would deliver for the simulated W1 setting.

    Full scale 3.49 Vpk; harmonics at -92/-100 dBc, flat noise at -108 dBFS/bin-ish, 50 Hz hum at -80 dBFS, a gentle
    top-end roll-off and a right channel 0.5 dB lower with -70 dB crosstalk. Numbers are plausible, not measured.
    """
    FS=48000;VFS=3.49
    def __init__(self,device):self.device=device;self.rng=np.random.default_rng(3);self.held=0.
    def hold(self,seconds):self.held=seconds
    def grab(self,seconds):
        n=int(seconds*self.FS);t=np.arange(n)/self.FS;w=self.device.w1;x=np.zeros(n)
        if w:
            kind,f,amp,off,shape=w;a=amp/self.VFS
            if kind=='sine':x=a*np.sin(2*np.pi*f*t)
            elif kind=='custom':x=a*np.interp((t*f)%1,np.linspace(0,1,len(shape),endpoint=False),shape,period=1)
            x=x+3e-5*x**2+1e-5*x**3          # -92 dBc second, -100 dBc third at full scale
            if self.device.fault=='missing-tone':x=np.zeros(n)
        x=x+1e-4*np.sin(2*np.pi*50*t)+self.rng.normal(0,4e-6,n)
        X=np.fft.rfft(x);fr=np.fft.rfftfreq(n,1/self.FS);X*=1/np.sqrt(1+(fr/24000)**8);x=np.fft.irfft(X,n)
        right=3e-4*x+self.rng.normal(0,4e-6,n)          # the other input is idle: -70 dB crosstalk and its own noise
        return np.vstack((x,right)).astype(np.float32)
