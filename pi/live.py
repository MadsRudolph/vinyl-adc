#!/usr/bin/env python3
"""Live view of what the Pi receives from the Vinyl ADC. Needs only NumPy.

    python3 live.py                 # on the Pi; then open http://vinyladc.local:8091 on the PC
    python3 live.py --replay x.raw  # anywhere: loop a saved capture instead of the sound card

It holds the capture device, so one-shot `arecord` runs fail while it is up; fetch
`/snapshot.raw` (the last 10 s of raw I2S words) instead and feed that to
analyze_bitstream.py or decimate.py. Read-only: it never writes to the ADC.
"""
import argparse,json,subprocess,sys,threading,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import numpy as np
import decimate as d

FS=d.FS_MOD;BLOCK_FRAMES=24000;BLOCK_BYTES=BLOCK_FRAMES*8;NFFT=1<<16;SEGMENTS=8;RING_BLOCKS=20
WIN=np.hanning(NFFT).astype(np.float32);WIN_POWER=float((WIN**2).sum())
FREQ=np.fft.rfftfreq(NFFT,1/FS)
EDGES=np.geomspace(20,FS/2,241);BIN_LO=np.searchsorted(FREQ,EDGES[:-1]);BIN_HI=np.maximum(np.searchsorted(FREQ,EDGES[1:]),BIN_LO+1)
PLOT_F=np.sqrt(EDGES[:-1]*EDGES[1:]);AUDIO=(FREQ>=20)&(FREQ<=20000)

class Channel:
    def __init__(self):self.cic=d.Cic();self.fir=d.FirDecimator(d.compensating_fir());self.psd=None;self.audio=np.zeros(0)
    def process(self,bits):
        x=bits.astype(np.float32)*2-1;P=np.zeros(NFFT//2+1)
        for k in range(SEGMENTS):
            seg=x[k*NFFT:(k+1)*NFFT];P+=np.abs(np.fft.rfft((seg-seg.mean())*WIN))**2
        P=P/(SEGMENTS*WIN_POWER*FS)*2
        self.psd=P if self.psd is None else .7*self.psd+.3*P      # a couple of seconds of averaging
        y=self.fir.process(self.cic.process(bits.astype(np.int8)*2-1));self.audio=np.concatenate((self.audio,y))[-48000:]
        at=lambda c:10*np.log10(np.median(self.psd[(FREQ>c/1.12)&(FREQ<c*1.12)])+1e-30)
        slope=(at(80e3)-at(30e3))/np.log10(80/30)
        runs=np.diff(np.flatnonzero(np.diff(bits.view(np.int8))!=0));mean_run=float(runs.mean()) if len(runs) else float(len(bits))
        inband=10*np.log10(float(self.psd[AUDIO].sum())*(FREQ[1]-FREQ[0])+1e-30)
        a=self.audio;ac=a-a.mean();density=float(bits.mean())
        if density<.02 or density>.98:verdict=('critical','Stuck bitstream')
        elif mean_run>4:verdict=('critical','Limit cycle: loop oscillating')
        elif slope>45:verdict=('good','Third-order shaping')
        elif slope>30:verdict=('warning','Weak shaping: one integrator')
        else:verdict=('serious','No noise shaping')
        plot=10*np.log10(np.array([self.psd[lo:hi].mean() for lo,hi in zip(BIN_LO,BIN_HI)])+1e-30)
        return {'density':density,'mean_run':mean_run,'max_run':int(runs.max()) if len(runs) else len(bits),'slope':float(slope),'inband_dbfs':float(inband),
                'floor_1k':float(at(1e3)),'floor_20k':float(at(2e4)),'dc':float(a.mean()) if len(a) else 0.,'rms_dbfs':float(20*np.log10(ac.std()+1e-12)) if len(a) else -200.,
                'peak_dbfs':float(20*np.log10(np.abs(ac).max()+1e-12)) if len(a) else -200.,'idle_tone_hz':abs(2*density-1)*FS,'verdict':verdict,
                'spectrum':[round(float(v),1) for v in plot],'wave':[round(float(v),6) for v in ac[-960:]],'bits':''.join(map(str,bits[:192]))}

class Monitor:
    def __init__(self,replay=None):
        self.replay=replay;self.lock=threading.Lock();self.state={'status':'starting','message':'Starting…','seq':0};self.ring=[]
    def source(self):
        if self.replay:
            data=open(self.replay,'rb').read();data=data[:len(data)//BLOCK_BYTES*BLOCK_BYTES]
            if not data:raise RuntimeError('Replay file holds less than one 0.5 s block')
            while True:
                for i in range(0,len(data),BLOCK_BYTES):
                    yield data[i:i+BLOCK_BYTES];time.sleep(.5)
        while True:
            p=subprocess.Popen(['arecord','-q','-D','hw:CARD=vinyladc','-c','2','-r','48000','-f','S32_LE','-t','raw','--buffer-time=500000','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                while True:
                    raw=p.stdout.read(BLOCK_BYTES)
                    if len(raw)<BLOCK_BYTES:break
                    yield raw
            finally:p.kill()
            err=p.stderr.read().decode(errors='replace').strip().splitlines()
            self.set(status='waiting',message='No clocks from the ADC, so nothing to record. Is the stack powered? '+(err[-1] if err else ''))
            time.sleep(2)
    def set(self,**kw):
        with self.lock:self.state={**kw,'seq':self.state['seq']+1,'time':time.time()}
    def run(self):
        chans=[Channel(),Channel()]
        for raw in self.source():
            t0=time.time();words=np.frombuffer(raw,dtype='<u4').reshape(-1,2);streams=d.split_bits(words)
            out=[c.process(b) for c,b in zip(chans,streams)]
            with self.lock:self.ring=(self.ring+[raw])[-RING_BLOCKS:]
            self.set(status='live',message='Replaying '+self.replay if self.replay else 'Live from the I2S capture card',freq=[round(float(f),1) for f in PLOT_F],
                     channels={'left':out[0],'right':out[1]},cpu_ms=round((time.time()-t0)*1000))

def handler(mon):
    class H(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def send(self,body,ctype,extra=()):
            self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            for k,v in extra:self.send_header(k,v)
            self.end_headers();self.wfile.write(body)
        def do_GET(self):
            path=self.path.split('?')[0]
            if path=='/':self.send(PAGE.encode(),'text/html; charset=utf-8')
            elif path=='/api/state':
                with mon.lock:body=json.dumps(mon.state).encode()
                self.send(body,'application/json')
            elif path=='/snapshot.raw':
                with mon.lock:body=b''.join(mon.ring)
                self.send(body,'application/octet-stream',[('Content-Disposition','attachment; filename="vinyl-adc-snapshot.raw"')])
            else:self.send_error(404)
    return H

PAGE=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vinyl ADC · live</title>
<style>
:root{color-scheme:dark;--surface:#1a1a19;--card:#232321;--grid:#33332f;--text:#fff;--text2:#c3c2b7;--muted:#8d8c83;--left:#3987e5;--right:#d95926;--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--text);font:15px/1.45 system-ui,sans-serif}
header{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline;padding:14px 22px;border-bottom:1px solid var(--grid)}h1{font-size:19px;margin:0}header span{color:var(--text2)}header a{color:var(--text2)}
main{padding:16px 22px;max-width:1500px;margin:0 auto;display:grid;gap:16px}
.channels{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:900px){.channels{grid-template-columns:1fr}}
.card{background:var(--card);border-radius:12px;padding:14px 16px}.card h2{font-size:15px;margin:0 0 2px;font-weight:600}.sub{color:var(--muted);font-size:13px;margin:0 0 8px}
.chead{display:flex;align-items:center;gap:10px;margin-bottom:10px}.swatch{width:14px;height:14px;border-radius:4px}.chead strong{font-size:16px}
.verdict{margin-left:auto;display:inline-flex;align-items:center;gap:7px;padding:3px 11px;border-radius:999px;background:#2d2d2a;font-size:13px;color:var(--text)}.verdict i{width:9px;height:9px;border-radius:50%;display:inline-block}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}@media(max-width:600px){.tiles{grid-template-columns:repeat(2,1fr)}}
.tile small{display:block;color:var(--muted);font-size:12px}.tile b{font-size:21px;font-weight:600;font-variant-numeric:tabular-nums}.tile em{font-style:normal;color:var(--text2);font-size:12px;margin-left:3px}
.legend{display:flex;gap:16px;color:var(--text2);font-size:13px;margin:0 0 6px}.legend span{display:inline-flex;align-items:center;gap:6px}.legend i{width:16px;height:3px;border-radius:2px;display:inline-block}
.plot{position:relative}canvas{width:100%;display:block}.tip{position:absolute;pointer-events:none;background:#0f0f0e;border:1px solid var(--grid);border-radius:8px;padding:6px 9px;font-size:12.5px;white-space:nowrap;display:none;font-variant-numeric:tabular-nums}
.tip i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.bits{display:grid;gap:6px;font-size:13px;color:var(--text2)}.bits canvas{height:18px}
details{color:var(--text2)}table{border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;margin-top:8px}td,th{padding:3px 12px 3px 0;text-align:right}th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-weight:500}
.banner{background:#3a2a12;border-left:4px solid var(--warning);padding:10px 14px;border-radius:8px}
</style>
<header><h1>Vinyl ADC · live</h1><span id="status">connecting…</span><span id="age"></span><a href="/snapshot.raw">Download last 10 s (raw)</a></header>
<main>
<div id="banner" class="banner" hidden></div>
<section class="channels" id="channels"></section>
<section class="card"><h2>Noise spectrum of the 1-bit streams, 20 Hz to 768 kHz</h2><p class="sub">Power density in dBFS/Hz, averaged over a few seconds. A healthy third-order loop is flat and low up to 20 kHz, then climbs about 60 dB per decade.</p>
<div class="legend"><span><i style="background:var(--left)"></i>Left</span><span><i style="background:var(--right)"></i>Right</span></div><div class="plot"><canvas id="spec" height="330"></canvas><div class="tip" id="spectip"></div></div></section>
<section class="card"><h2>Decimated audio, last 20 ms</h2><p class="sub">48 kHz output with each channel's DC removed; the vertical scale follows the larger channel. With the inputs shorted this is the noise floor.</p>
<div class="legend"><span><i style="background:var(--left)"></i>Left</span><span><i style="background:var(--right)"></i>Right</span></div><div class="plot"><canvas id="wave" height="220"></canvas><div class="tip" id="wavetip"></div></div></section>
<section class="card"><h2>First 192 modulator bits of the latest block</h2><p class="sub">Filled = 1. A working loop looks like fine, irregular hatching; long solid bars are a limit cycle.</p>
<div class="bits"><div>Left<canvas id="bitsL" height="18"></canvas></div><div>Right<canvas id="bitsR" height="18"></canvas></div></div></section>
<details class="card"><summary>Table view</summary><div id="table"></div></details>
</main>
<script>
const $=s=>document.querySelector(s),css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const COL={left:css('--left'),right:css('--right')},NAMES={left:'Left',right:'Right'},STATUS={good:['--good','●'],warning:['--warning','▲'],serious:['--serious','◆'],critical:['--critical','■']};
let S=null,hover={spec:null,wave:null};
const fmt=(v,d=1)=>Number(v).toFixed(d),fhz=f=>f>=1000?(f/1000>=100?fmt(f/1000,0):fmt(f/1000,1))+' kHz':fmt(f,0)+' Hz';
function tiles(){const box=$('#channels');box.innerHTML=['left','right'].map(k=>{const c=S.channels[k],[tok,icon]=STATUS[c.verdict[0]];return `<div class="card"><div class="chead"><span class="swatch" style="background:${COL[k]}"></span><strong>${NAMES[k]} channel</strong><span class="verdict"><i style="background:var(${tok})"></i>${icon} ${c.verdict[1]}</span></div>
<div class="tiles"><div class="tile"><small>Noise, 20 Hz–20 kHz</small><b>${fmt(c.inband_dbfs)}</b><em>dBFS</em></div><div class="tile"><small>Shaping, 30→80 kHz</small><b>${c.slope>=0?'+':''}${fmt(c.slope,0)}</b><em>dB/decade</em></div><div class="tile"><small>One-density</small><b>${fmt(c.density,4)}</b><em>0.5 = zero input</em></div><div class="tile"><small>Mean run of equal bits</small><b>${fmt(c.mean_run,2)}</b><em>max ${c.max_run}</em></div>
<div class="tile"><small>Audio peak (1 s)</small><b>${fmt(c.peak_dbfs)}</b><em>dBFS</em></div><div class="tile"><small>DC offset</small><b>${c.dc>=0?'+':''}${fmt(c.dc,4)}</b><em>FS</em></div><div class="tile"><small>Floor at 1 kHz</small><b>${fmt(c.floor_1k)}</b><em>dBFS/Hz</em></div><div class="tile"><small>Idle tone expected near</small><b>${fhz(c.idle_tone_hz)}</b></div></div></div>`}).join('')}
function setup(cv){const r=devicePixelRatio||1,w=cv.clientWidth,h=+cv.getAttribute('height');cv.width=w*r;cv.height=h*r;cv.style.height=h+'px';const g=cv.getContext('2d');g.setTransform(r,0,0,r,0,0);g.clearRect(0,0,w,h);g.font='12px system-ui,sans-serif';return [g,w,h]}
function drawSpec(){const cv=$('#spec'),[g,w,h]=setup(cv),m={l:48,r:54,t:10,b:26},f=S.freq,lo=Math.log10(20),hi=Math.log10(768000),ymin=-140,ymax=-40;
 const X=v=>m.l+(Math.log10(v)-lo)/(hi-lo)*(w-m.l-m.r),Y=v=>m.t+(ymax-Math.max(ymin,Math.min(ymax,v)))/(ymax-ymin)*(h-m.t-m.b);
 g.strokeStyle=css('--grid');g.fillStyle=css('--muted');g.lineWidth=1;g.textAlign='right';g.textBaseline='middle';
 for(let v=ymin;v<=ymax;v+=20){g.beginPath();g.moveTo(m.l,Y(v)+.5);g.lineTo(w-m.r,Y(v)+.5);g.stroke();g.fillText(v,m.l-8,Y(v))}
 g.textAlign='center';g.textBaseline='top';for(const v of [100,1e3,1e4,1e5]){g.beginPath();g.moveTo(X(v)+.5,m.t);g.lineTo(X(v)+.5,h-m.b);g.stroke();g.fillText(fhz(v),X(v),h-m.b+7)}
 g.fillText('dBFS/Hz',m.l-20,0);g.strokeStyle=css('--muted');g.beginPath();g.moveTo(X(2e4)+.5,m.t);g.lineTo(X(2e4)+.5,h-m.b);g.stroke();g.textAlign='left';g.fillText('20 kHz: end of the audio band',X(2e4)+6,m.t+2);
 for(const k of ['right','left']){const s=S.channels[k].spectrum;g.strokeStyle=COL[k];g.lineWidth=2;g.lineJoin=g.lineCap='round';g.beginPath();s.forEach((v,i)=>i?g.lineTo(X(f[i]),Y(v)):g.moveTo(X(f[i]),Y(v)));g.stroke();
  const e=s.length-1;g.fillStyle=css('--surface');g.beginPath();g.arc(X(f[e]),Y(s[e]),6,0,7);g.fill();g.fillStyle=COL[k];g.beginPath();g.arc(X(f[e]),Y(s[e]),4,0,7);g.fill();g.fillStyle=css('--text2');g.textAlign='left';g.textBaseline='middle';g.fillText(NAMES[k],X(f[e])+9,Y(s[e])+(k==='left'?-7:7))}
 cv._map={X,Y,m,w,h};if(hover.spec!==null)cross(cv,'spec')}
function drawWave(){const cv=$('#wave'),[g,w,h]=setup(cv),m={l:64,r:54,t:10,b:24},L=S.channels.left.wave,R=S.channels.right.wave,n=L.length;let a=1e-6;for(const v of L.concat(R))a=Math.max(a,Math.abs(v));a*=1.15;
 const X=i=>m.l+i/(n-1)*(w-m.l-m.r),Y=v=>m.t+(a-v)/(2*a)*(h-m.t-m.b);g.strokeStyle=css('--grid');g.fillStyle=css('--muted');g.textAlign='right';g.textBaseline='middle';
 for(const v of [-a/1.15,0,a/1.15]){g.beginPath();g.moveTo(m.l,Y(v)+.5);g.lineTo(w-m.r,Y(v)+.5);g.stroke();g.fillText((v>=0?'+':'')+v.toExponential(1),m.l-8,Y(v))}
 g.textAlign='center';g.textBaseline='top';for(let t=0;t<=20;t+=5){const i=t/20*(n-1);g.beginPath();g.moveTo(X(i)+.5,m.t);g.lineTo(X(i)+.5,h-m.b);g.stroke();g.fillText(t+' ms',X(i),h-m.b+6)}g.fillText('FS',m.l-20,0);
 for(const [k,s] of [['right',R],['left',L]]){g.strokeStyle=COL[k];g.lineWidth=2;g.lineJoin=g.lineCap='round';g.beginPath();s.forEach((v,i)=>i?g.lineTo(X(i),Y(v)):g.moveTo(X(i),Y(v)));g.stroke();g.fillStyle=css('--text2');g.textAlign='left';g.textBaseline='middle';g.fillText(NAMES[k],w-m.r+8,Y(s[n-1])+(k==='left'?-7:7))}
 cv._map={X,Y,m,w,h,n};if(hover.wave!==null)cross(cv,'wave')}
function cross(cv,which){const g=cv.getContext('2d'),{X,Y,m,h}=cv._map,i=hover[which],x=which==='spec'?X(S.freq[i]):X(i);g.strokeStyle=css('--text2');g.lineWidth=1;g.beginPath();g.moveTo(x+.5,m.t);g.lineTo(x+.5,h-m.b);g.stroke();
 for(const k of ['left','right']){const v=which==='spec'?S.channels[k].spectrum[i]:S.channels[k].wave[i];g.fillStyle=css('--surface');g.beginPath();g.arc(x,Y(v),6,0,7);g.fill();g.fillStyle=COL[k];g.beginPath();g.arc(x,Y(v),4,0,7);g.fill()}
 const tip=$(which==='spec'?'#spectip':'#wavetip'),head=which==='spec'?fhz(S.freq[i]):fmt(i/48,2)+' ms',val=k=>which==='spec'?fmt(S.channels[k].spectrum[i])+' dBFS/Hz':(S.channels[k].wave[i]>=0?'+':'')+S.channels[k].wave[i].toExponential(2)+' FS';
 tip.innerHTML=`<strong>${head}</strong><br><i style="background:${COL.left}"></i>Left ${val('left')}<br><i style="background:${COL.right}"></i>Right ${val('right')}`;tip.style.display='block';tip.style.left=Math.min(x+12,cv.clientWidth-190)+'px';tip.style.top=(m.t+4)+'px'}
function track(id,which){const cv=$(id);cv.addEventListener('mousemove',e=>{if(!S||!cv._map)return;const r=cv.getBoundingClientRect(),x=e.clientX-r.left,{X}=cv._map;let best=0,bd=1e9;const n=which==='spec'?S.freq.length:cv._map.n;for(let i=0;i<n;i++){const dx=Math.abs((which==='spec'?X(S.freq[i]):X(i))-x);if(dx<bd){bd=dx;best=i}}hover[which]=best;which==='spec'?drawSpec():drawWave()});
 cv.addEventListener('mouseleave',()=>{hover[which]=null;$(which==='spec'?'#spectip':'#wavetip').style.display='none';which==='spec'?drawSpec():drawWave()})}
function drawBits(id,k){const cv=$(id),[g,w,h]=setup(cv),b=S.channels[k].bits,cw=w/b.length;g.fillStyle=css('--grid');g.fillRect(0,0,w,h);g.fillStyle=COL[k];for(let i=0;i<b.length;i++)if(b[i]==='1')g.fillRect(i*cw,0,Math.max(1,cw-.6),h)}
function table(){const pick=[100,1000,5000,20000,50000,100000,200000,500000],idx=pick.map(p=>S.freq.reduce((b,f,i)=>Math.abs(Math.log(f/p))<Math.abs(Math.log(S.freq[b]/p))?i:b,0));
 $('#table').innerHTML='<table><tr><th>Noise density, dBFS/Hz</th>'+pick.map(p=>`<th>${fhz(p)}</th>`).join('')+'</tr>'+['left','right'].map(k=>`<tr><td>${NAMES[k]}</td>`+idx.map(i=>`<td>${fmt(S.channels[k].spectrum[i])}</td>`).join('')+'</tr>').join('')+'</table>'}
async function poll(){try{const s=await (await fetch('/api/state')).json();$('#status').textContent=s.message||s.status;const b=$('#banner');
 if(s.status==='live'){S=s;b.hidden=true;$('#age').textContent='block '+s.seq+' · '+s.cpu_ms+' ms to process 0.5 s';tiles();drawSpec();drawWave();drawBits('#bitsL','left');drawBits('#bitsR','right');table()}
 else{b.hidden=false;b.textContent=s.message}}catch(e){$('#status').textContent='lost contact with the Pi'}setTimeout(poll,500)}
track('#spec','spec');track('#wave','wave');addEventListener('resize',()=>{if(S){drawSpec();drawWave()}});poll();
</script></html>'''

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port',type=int,default=8091);p.add_argument('--replay',help='loop a saved .raw capture instead of recording')
    a=p.parse_args();mon=Monitor(a.replay);threading.Thread(target=mon.run,daemon=True).start()
    print(f'Vinyl ADC live view on port {a.port}',flush=True)
    ThreadingHTTPServer(('0.0.0.0',a.port),handler(mon)).serve_forever()
if __name__=='__main__':main()
