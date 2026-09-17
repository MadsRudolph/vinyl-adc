#!/usr/bin/env python3
"""Judge each channel's modulator from a raw capture, at the full 1.536 MHz bit rate. Needs only NumPy.

    python3 analyze_bitstream.py capture.raw

A healthy third-order loop has a flat in-band floor and noise that climbs about 60 dB/decade just above the
audio band. A loop that climbs ~20 dB/decade and carries a strong idle tone at |DC| x 1.536 MHz is running
first-order: one or two integrators are stuck, clamped or mis-valued.
"""
import sys
import numpy as np
import decimate as d

FS=d.FS_MOD;N=1<<16
def psd(bits):
    x=bits.astype(np.float32)*2-1;x=x[int(.3*FS):];n=len(x)//N;win=np.hanning(N);P=np.zeros(N//2+1)
    if n<8:sys.exit('Capture too short: record at least 2 seconds')
    for k in range(n):
        seg=x[k*N:(k+1)*N];P+=np.abs(np.fft.rfft((seg-seg.mean())*win))**2
    return P/(n*(win**2).sum()*FS)*2
def integrate(P,f,m):return float(np.sum(P[m])*(f[1]-f[0]))
def main(path):
    streams=[[],[]]
    for w in d.frames_from(path):
        for i,b in enumerate(d.split_bits(w)):streams[i].append(b)
    f=np.fft.rfftfreq(N,1/FS);band=(f>=20)&(f<=20000)
    for i,name in enumerate(('bitstream 0 (left)','bitstream 1 (right)')):
        bits=np.concatenate(streams[i]);P=psd(bits);density=bits.mean()
        at=lambda c:10*np.log10(np.median(P[(f>c/1.12)&(f<c*1.12)]))
        slope=(at(80e3)-at(30e3))/np.log10(80/30)
        k=np.argmax(P[band]);fk=f[band][k];j=np.argmin(np.abs(f-fk));tone=10*np.log10(P[max(0,j-2):j+3].sum()*(f[1]-f[0]))
        Pn=P.copy()
        for h in (1,2,3):
            jh=np.argmin(np.abs(f-h*fk));Pn[max(0,jh-3):jh+4]=np.median(P[max(0,jh-40):jh+40])
        total=10*np.log10(integrate(P,f,band));floor=10*np.log10(integrate(Pn,f,band))
        verdict='third-order shaping, healthy' if slope>45 else 'second-order-like: one integrator weak' if slope>30 else 'FIRST-ORDER-LIKE: integrators stuck, clamped or mis-valued'
        print(f'{name}: one-density {density:.4f}')
        print(f'   in-band floor {at(1e3):.1f} / {at(5e3):.1f} / {at(2e4):.1f} dBFS/Hz at 1 / 5 / 20 kHz')
        print(f'   shaping 30→80 kHz: {slope:+.0f} dB/decade  → {verdict}')
        print(f'   20 Hz–20 kHz: total {total:.1f} dBFS; strongest line {fk:.0f} Hz at {tone:.1f} dBFS (idle tone expected near {abs(2*density-1)*FS:.0f} Hz); floor without it {floor:.1f} dBFS')
if __name__=='__main__':
    if len(sys.argv)!=2:sys.exit(__doc__)
    main(sys.argv[1])
