"""Synthetic fixtures for exercising scripts without any device. Never hardware evidence."""
import numpy as np

class SimulatedAD3:
    def __init__(self,fault=None):self.fault=fault;self.info={'serial':'SIMULATED','name':'Synthetic fixture','sdk':'none'};self.cleanup_errors=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def wave(self,*args):pass
    def wave_off(self):pass
    def supply_3v3(self,*args):pass
    def scope_fixture(self,kind,rate,count):
        t=np.arange(count)/rate;rng=np.random.default_rng(19)
        sine=lambda amp:amp*np.sin(2*np.pi*1000*t)
        square=lambda f,v:v*((t*f)%1<.5)
        if kind=='pump-check':a,b=square(192000,5),np.zeros(count)
        elif kind=='rails-power' or kind=='rails-channel':a,b=np.full(count,5.),np.full(count,-4.1)
        elif kind=='rails-digital':a,b=np.full(count,5.),np.full(count,3.3)
        elif kind=='references':a,b=np.full(count,2.5),np.full(count,-2.5)
        elif kind=='clocks':a,b=square(3072000,3.3),square(48000,3.3)
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
