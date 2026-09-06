"""Measurement analysis shared by real acquisitions and offline fixture tests."""
import numpy as np

def bit(words,channel):return ((words>>channel)&1).astype(np.uint8)
def edges(x,rising=True):
    x=np.asarray(x,dtype=np.int8);return np.flatnonzero(np.diff(x)==(1 if rising else -1))+1

def frequency(x,rate):
    rise=edges(x)
    if len(rise)<3:raise ValueError('Fewer than three rising edges: missing/stuck clock or capture too short')
    return float((len(rise)-1)*rate/(rise[-1]-rise[0]))

def summary(x):
    x=np.asarray(x,dtype=float)
    if len(x)<8 or not np.isfinite(x).all():raise ValueError('Insufficient or non-finite analog samples')
    return {'mean_v':float(x.mean()),'vpp':float(np.ptp(x)), 'low_v':float(np.quantile(x,.05)), 'high_v':float(np.quantile(x,.95)), 'ac_rms_v':float(x.std())}

def sine_fit(x,rate,freq):
    x=np.asarray(x,dtype=float);t=np.arange(len(x))/rate
    design=np.column_stack([np.sin(2*np.pi*freq*t),np.cos(2*np.pi*freq*t),np.ones(len(x))])
    fit=np.linalg.lstsq(design,x,rcond=None)[0];residual=x-design@fit;energy=float(np.sum((x-x.mean())**2))
    return {'amplitude':float(np.hypot(*fit[:2])),'r2':float(1-np.sum(residual**2)/energy) if energy>1e-20 else 0.0,'offset':float(fit[2])}

def stable_mask(words,channels,guard=5):
    mask=np.ones(len(words),dtype=bool)
    for ch in channels:
        transitions=np.flatnonzero(np.diff(bit(words,ch)))+1
        for delta in range(-guard,guard+1):mask[np.clip(transitions+delta,0,len(words)-1)]=False
    mask[:guard+1]=False;mask[-guard-1:]=False
    return mask

def mux_errors(words,rate=50e6):
    # DIO1=MCLK, DIO7=QL, DIO8=QR, DIO6=DIN, DIO9=PI_DIN.
    mask=stable_mask(words,[1,7,8],max(1,int(np.ceil(rate*120e-9))))  # settle around selector transitions
    if np.count_nonzero(mask)<100:raise ValueError('Too few settled mux samples')
    expected=np.where(bit(words,1),bit(words,7),bit(words,8))
    return {name:float(np.mean(bit(words,ch)[mask]!=expected[mask])) for name,ch in [('mux_error',6),('pi_error',9)]}

def channel_stream(words,rate):
    clock=bit(words,0);fall=edges(clock,False)
    if len(fall)<1000:raise ValueError('Too few modulator clock cycles')
    q=bit(words,1);bits=q[fall]
    clock_hz=frequency(clock,rate)
    block=256;n=len(bits)//block
    audio=bits[:n*block].reshape(n,block).mean(axis=1)
    # Endpoints measured from actual clock cycles, not an assumed 1.536 MHz rate.
    return {'bits':bits,'audio':audio,'audio_rate':clock_hz/block,'clock_hz':clock_hz,'density':float(bits.mean()),'transitions':int(np.count_nonzero(np.diff(bits)))}

def dac_errors(words):
    # DIO1=Q, 2=/Q, 3=DACP, 4=DACN. Exclude uncertain transition samples.
    mask=stable_mask(words,[1,2,3,4],1)
    if np.count_nonzero(mask)<100:raise ValueError('Too few settled DAC samples')
    q=bit(words,1)
    return {name:float(np.mean(bit(words,ch)[mask]!=expected[mask])) for name,ch,expected in [('qn_error',2,1-q),('dacp_error',3,q),('dacn_error',4,1-q)]}


def clock_delay_ns(source,output,rate):
    a,b=edges(source),edges(output)
    if len(a)<3 or len(b)<3:raise ValueError('Missing edges for clock polarity check')
    idx=np.searchsorted(a,b,side='right')-1
    valid=(idx>=0)&(idx<len(a)-1);idx=idx[valid];b=b[valid]
    if len(b)<3:raise ValueError('Too few matching clock edges')
    period=float(np.median(np.diff(a)));delta=(b-a[idx]).astype(float)
    delta[delta>period/2]-=period
    return float(np.median(delta)/rate*1e9)
