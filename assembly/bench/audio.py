"""Audio performance of the finished ADC: the AD3 drives the channel input, the Pi's ripper delivers the decimated
48 kHz audio it would record, and this module turns that into the usual converter figures (THD+N, SNR, dynamic
range, frequency response, IMD, crosstalk). Used by run.py's `audio` plan; plots and a Markdown table land in
the run folder for the write-up.

All levels are dBFS of the decimated output (1.0 = full scale of the modulator). The AD3's own generator sets a
floor of roughly -80 dB on distortion and noise figures; anything measured better than that is the generator.
"""
import json,time,urllib.request
import numpy as np
FS=48000

# ---- talking to the Pi
class PiAudio:
    """/api/audio on the ripper: the last N seconds of what it decimated. /api/hold keeps it from recording the test tones as a side."""
    def __init__(self,url):self.url=url.rstrip('/')
    def hold(self,seconds):
        req=urllib.request.Request(self.url+'/api/hold',data=json.dumps({'seconds':seconds}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=10) as r:return json.loads(r.read())
    def grab(self,seconds):
        with urllib.request.urlopen(f'{self.url}/api/audio?seconds={int(np.ceil(seconds))}',timeout=30) as r:raw=r.read()
        x=np.frombuffer(raw,dtype='<f4').reshape(-1,2).T
        if x.shape[1]<seconds*FS*.9:raise RuntimeError(f'The Pi returned {x.shape[1]/FS:.1f} s of audio; is the ripper running and the ADC clocking?')
        return x[:,-int(seconds*FS):]

# ---- spectra and figures
def spectrum(x):
    """Power spectrum (linear, per bin) of a Hann-windowed record in dBFS units: a full-scale sine sums to 1.0 over its
    bins, and noise sums to 2*variance, i.e. levels are rms relative to the rms of a full-scale sine (AES17 dBFS)."""
    n=len(x);w=np.hanning(n);X=np.fft.rfft(x*w)/np.sum(w)*2;P=np.abs(X)**2/1.5      # Hann: centre bin A^2, neighbours A^2/4 each -> sum 1.5 A^2
    return np.fft.rfftfreq(n,1/FS),P
def band_power(f,P,f0,half_bins=4):
    i=int(np.argmin(np.abs(f-f0)));return float(P[max(0,i-half_bins):i+half_bins+1].sum())
def db(p):return float(10*np.log10(max(p,1e-30)))
def a_weight(f):
    f2=f**2;r=12194.**2*f2**2/((f2+20.6**2)*np.sqrt((f2+107.7**2)*(f2+737.9**2))*(f2+12194.**2));return r/0.7943   # 0 dB at 1 kHz
def tone_figures(x,f0,weighted=False):
    """THD, THD+N and the fundamental's level for a captured sine. Harmonics up to 20 kHz; noise band 20 Hz-20 kHz."""
    f,P=spectrum(x);inband=(f>=20)&(f<=20000);W=a_weight(f) if weighted else np.ones_like(f)
    fund=band_power(f,P,f0);harm=[band_power(f,P,k*f0) for k in range(2,int(20000//f0)+1)]
    rest=max(1e-30,float((P*W)[inband].sum())-band_power(f,P*W,f0))   # everything in band except the fundamental: harmonics + noise (clamped: a 20 kHz tone's bins straddle the band edge)
    return {'level_dbfs':db(fund),'thd_db':db(sum(harm))-db(fund),'thd_pct':100*np.sqrt(sum(harm)/max(fund,1e-30)),'thdn_db':db(rest)-db(fund),'thdn_pct':100*np.sqrt(rest/max(fund,1e-30)),
            'harmonics_dbc':[db(h)-db(fund) for h in harm[:5]],'noise_dbfs':db(rest-sum(harm) if rest>sum(harm) else rest)}
def noise_figures(x):
    f,P=spectrum(x);inband=(f>=20)&(f<=20000);W=a_weight(f)
    hum={int(h):db(band_power(f,P,h,2)) for h in (50,100,150,200)}
    return {'noise_dbfs':db(P[inband].sum()),'noise_dbfs_a':db((P*W)[inband].sum()),'hum_dbfs':hum,'peak_bin_hz':float(f[inband][np.argmax(P[inband])])}
def imd_ccif(x,f1=19000.,f2=20000.):
    f,P=spectrum(x);ref=band_power(f,P,f1)+band_power(f,P,f2);d2=band_power(f,P,f2-f1);d3=band_power(f,P,2*f1-f2)
    return {'imd_d2_db':db(d2)-db(ref),'imd_d3_db':db(d3)-db(ref),'imd_pct':100*np.sqrt((d2+d3)/max(ref,1e-30))}
def imd_smpte(x,lo=60.,hi=7000.):
    f,P=spectrum(x);ref=band_power(f,P,hi);side=sum(band_power(f,P,hi+k*lo) for k in (-2,-1,1,2))
    return {'imd_db':db(side)-db(ref),'imd_pct':100*np.sqrt(side/max(ref,1e-30))}
def two_tone(f1,f2,r1=1.,r2=1.,n=4096):
    """One period (at gcd frequency) of two sines with the given relative amplitudes, normalised to +-1. Returns (repetition Hz, shape)."""
    import math;g=math.gcd(int(f1),int(f2));t=np.arange(n)/n;y=r1*np.sin(2*np.pi*(f1//g)*t)+r2*np.sin(2*np.pi*(f2//g)*t);return float(g),y/np.abs(y).max()
def sweep_points(lo=20.,hi=20000.,per_octave=3):
    k=np.arange(0,int(np.ceil(np.log2(hi/lo)*per_octave))+1);f=lo*2**(k/per_octave);f=f[f<=hi]
    return [float(round(v,1)) for v in np.unique(np.r_[f,1000.])]
def bin_centred(f0,seconds):
    """Snap a test frequency onto an FFT bin of a `seconds` long record so the Hann leakage is symmetric."""
    return float(round(f0*seconds)/seconds)

# ---- write-up
def plot_spectrum(path,x,title,f0=None):
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    f,P=spectrum(x);fig,ax=plt.subplots(figsize=(9,4.2),dpi=110);ax.semilogx(f[1:],10*np.log10(P[1:]+1e-30),lw=.7,color='#3987e5')
    ax.set_xlim(10,24000);ax.set_ylim(-150,5);ax.set_xlabel('Hz');ax.set_ylabel('dBFS per bin');ax.set_title(title);ax.grid(True,which='both',alpha=.3)
    if f0:ax.axvline(f0,color='#d95926',lw=.6,alpha=.6)
    fig.tight_layout();fig.savefig(path);plt.close(fig)
def plot_response(path,freqs,gains_db,title):
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,3.6),dpi=110);ax.semilogx(freqs,gains_db,'o-',ms=4,lw=1,color='#3987e5');ax.set_xlim(15,24000)
    lo=min(-3,float(np.nanmin(gains_db))-.5);ax.set_ylim(lo,max(1,float(np.nanmax(gains_db))+.5));ax.set_xlabel('Hz');ax.set_ylabel('dB re 1 kHz');ax.set_title(title);ax.grid(True,which='both',alpha=.3)
    fig.tight_layout();fig.savefig(path);plt.close(fig)
def summary_markdown(report):
    """A table of the audio figures from a finished report, for the portfolio write-up."""
    rows=[];notes=report.get('audio',{})
    for step in report['steps']:
        for m in step['metrics']:rows.append((step['id'],m['name'],m['value'],m['unit']))
    out=[f"# Audio performance — {report['id']}",'',f"Channel: {notes.get('channel','?')} · full scale {notes.get('vfs_peak','?')} Vpk · generator: AD3 W1 · capture: Pi ripper, 48 kHz decimated output",
         '','| Step | Measurement | Value | Unit |','|---|---|---:|---|']
    out+=[f'| {s} | {n} | {v:.4g} | {u} |' if isinstance(v,(int,float)) else f'| {s} | {n} | {v} | {u} |' for s,n,v,u in rows]
    out+=['','Reference points: 16-bit CD 96 dB dynamic range, 98 dB SNR; a good vinyl pressing 60-70 dB; the AD3 generator limits measured distortion and noise to about -80 dB.']
    return '\n'.join(out)+'\n'
