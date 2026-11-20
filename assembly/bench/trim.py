#!/usr/bin/env python3
"""Live RV20 trim meter: AD3 W1 plays a 1 kHz sine into one channel input, the ripper's
decimated audio is read back from the Pi, and the 1 kHz level is printed twice a second.

Turn RV20 until the channel under test reads the target (default -19.8 dBFS for 0.5 Vpk,
which is a 4.9 Vpk full scale: the rev D record-playing setting, music peaks near -6 dBFS).
Ctrl+C stops; W1 is switched off on exit.

    LD_LIBRARY_PATH=/usr/lib/digilent/adept python3 trim.py [--seconds 600] [--target -19.8]
"""
import argparse,json,math,sys,time,urllib.request
import numpy as np
from dwf_device import AD3

p=argparse.ArgumentParser()
p.add_argument('--pi',default='http://vinyladc.local:8091')
p.add_argument('--vpk',type=float,default=.5)
p.add_argument('--target',type=float,default=-19.8)
p.add_argument('--seconds',type=float,default=900)
a=p.parse_args()

def post(path,body):
    urllib.request.urlopen(urllib.request.Request(a.pi+path,json.dumps(body).encode(),{'Content-Type':'application/json'}),timeout=5).read()

def level():
    r=urllib.request.urlopen(a.pi+'/api/audio?seconds=1',timeout=5);fs=int(r.headers['X-Rate'])
    x=np.frombuffer(r.read(),'<f4').reshape(-1,2).astype(np.float64)[-fs//2:]
    t=np.arange(len(x))/fs;s=np.sin(2*np.pi*1000*t);c=np.cos(2*np.pi*1000*t);out=[]
    for ch in range(2):
        y=x[:,ch]-x[:,ch].mean();amp=2*math.hypot(y@s,y@c)/len(y)
        out.append(20*math.log10(amp+1e-12))
    return out

post('/api/hold',{'seconds':a.seconds+60})
with AD3() as dev:
    dev.wave('sine',1000.,a.vpk);time.sleep(1.5);end=time.time()+a.seconds
    print(f'W1: 1 kHz, {a.vpk} Vpk. Target {a.target:+.1f} dBFS on the channel under test. Ctrl+C to stop.\n')
    try:
        while time.time()<end:
            L,R=level();hot=0 if L>R else 1;v=(L,R)[hot]
            d=v-a.target;arrow='OK' if abs(d)<.3 else ('turn DOWN' if d>0 else 'turn UP')
            fs_v=a.vpk/10**(v/20)
            sys.stdout.write(f'\rL {L:7.2f}  R {R:7.2f} dBFS | {"LR"[hot]} is {d:+5.2f} dB from target, full scale {fs_v:5.2f} Vpk  {arrow:9s}');sys.stdout.flush()
            time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:dev.wave_off()
print('\nW1 off.')
post('/api/hold',{'seconds':0})
