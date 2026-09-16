#!/usr/bin/env python3
"""Local browser front end for the AD3 board tests in run.py.

Serves on 127.0.0.1 only. The page shows each step's wiring and relays the
operator's READY / ON / OFF confirmations and current readings to run.py; it
never enables an instrument output by itself and never controls the bench
supply. One run at a time; the same report files as the terminal route.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
if __name__=='__main__' and sys.platform.startswith('linux') and Path('/usr/lib/digilent/adept').is_dir():
    paths=os.environ.get('LD_LIBRARY_PATH','').split(':')
    if '/usr/lib/digilent/adept' not in paths:
        env=os.environ.copy();env['LD_LIBRARY_PATH']=':'.join(['/usr/lib/digilent/adept']+[x for x in paths if x])
        os.execve(sys.executable,[sys.executable,*sys.argv],env)
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import numpy as np
import run as runner
from dwf_device import SDK,InstrumentError

HERE=Path(__file__).resolve().parent

class WebOperator:
    """Blocks the test thread on each prompt until the browser answers. Abort raises KeyboardInterrupt at the next prompt."""
    def __init__(self):
        self.lock=threading.Lock();self.events=[];self.pending=None;self.answer_value=None;self.answered=threading.Event();self.aborted=False;self.counter=0
    def emit(self,**event):
        with self.lock:self.counter+=1;event['seq']=self.counter;self.events.append(event)
    def say(self,text):self.emit(kind='text',text=text)
    def show_step(self,step,extra):self.emit(kind='step',step=step,extra=extra)
    def metric(self,m):self.emit(kind='metric',**m)
    def finished(self,report):self.emit(kind='finished',status=report['status'],error=report.get('error'),id=report['id'])
    def _wait(self,kind,message,word=None):
        with self.lock:
            if self.aborted:raise KeyboardInterrupt
            self.counter+=1;self.pending={'id':self.counter,'kind':kind,'message':message,'word':word};self.answered.clear()
        self.emit(**dict(self.pending,kind='prompt',prompt_kind=self.pending['kind']))
        self.answered.wait()
        with self.lock:
            value=self.answer_value;self.pending=None;self.answer_value=None
            if self.aborted:raise KeyboardInterrupt
        return value
    def prompt(self,message,word):
        value=self._wait('confirm',message,word)
        self.emit(kind='answer',text=word)
        if str(value).strip().upper()!=word:raise KeyboardInterrupt
    def ask_current(self):
        while True:
            value=self._wait('current','Record the +5 V bench current in mA')
            try:
                value=float(value)
                if not np.isfinite(value) or value<0:raise ValueError()
                self.emit(kind='answer',text=f'{value:g} mA');return value
            except (TypeError,ValueError):self.say('Enter a finite, nonnegative reading in mA.')
    def answer(self,prompt_id,value):
        with self.lock:
            if not self.pending or self.pending['id']!=prompt_id:return False
            self.answer_value=value;self.answered.set();return True
    def abort(self):
        with self.lock:self.aborted=True;self.answered.set()
        self.emit(kind='text',text='Abort requested. The run stops at the next prompt and shuts down AD3 outputs.')

class Session:
    def __init__(self):self.lock=threading.Lock();self.op=None;self.run=None;self.thread=None;self.settings=None
    def active(self):return self.thread is not None and self.thread.is_alive()
    def start(self,settings):
        with self.lock:
            if self.active():raise RuntimeError('A run is already in progress')
            argv=[settings['board'],'--probe',settings['probe']]
            if settings.get('ad3_3v3'):argv.append('--ad3-3v3')
            if settings.get('resume'):argv+=['--resume',settings['resume']]
            if settings.get('serial'):argv+=['--serial',settings['serial']]
            if settings.get('simulate'):argv.append('--simulate')  # offline self-test of the page; reports stay SIMULATED
            p=runner.build_parser()
            try:args=p.parse_args(argv)
            except SystemExit:raise RuntimeError('Invalid settings: '+' '.join(argv))
            if args.board=='power':args.ad3_3v3=False
            runner.validate_args(p,args)
            op=WebOperator();run=runner.Run(args,op)
            self.op,self.run,self.settings=op,run,dict(settings,run_id=run.run_id,argv=argv)
            self.thread=threading.Thread(target=run.execute,name='bench-run',daemon=True);self.thread.start()
            return run.run_id
    def state(self,since=0):
        op=self.op
        with self.lock:
            events=[e for e in op.events if e['seq']>since] if op else []
            pending=dict(op.pending) if op and op.pending else None
            report=self.run.report if self.run else None
            return {'running':self.active(),'settings':self.settings,'status':report['status'] if report else None,'steps':[{'id':s['id'],'status':s['status'],'carried_from':s.get('carried_from')} for s in report['steps']] if report else [],'pending':pending,'events':events}

SESSION=Session()

def resumable_reports(board):
    out=[]
    for r in runner.write_index(runner.HERE/'results'):
        if r.get('board')!=board or r.get('simulated'):continue
        try:full=json.loads((runner.HERE/'results'/r['id']/'report.json').read_text())
        except (OSError,ValueError):continue
        passed=[]
        for key in runner.STEP_ORDER[board]:
            step=next((s for s in full.get('steps',[]) if s['id']==key),None)
            if not step or step.get('status')!='PASS':break
            passed.append(key)
        out.append({'id':r['id'],'status':r['status'],'started':r['started'],'passed':passed,'scope_inputs':r.get('scope_inputs'),'resumable':bool(passed) and r['status']!='PASS'})
    return out

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send_json(self,payload,code=200):
        body=json.dumps(payload).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        path,_,query=self.path.partition('?');params=dict(x.split('=',1) for x in query.split('&') if '=' in x)
        if path=='/':
            body=PAGE.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        elif path=='/api/state':self.send_json(SESSION.state(int(params.get('since','0') or 0)))
        elif path=='/api/reports':self.send_json(resumable_reports(params.get('board','power')))
        elif path=='/api/devices':
            try:self.send_json(SDK().devices())
            except InstrumentError as e:self.send_json({'error':str(e),'devices':[]})
        elif path=='/api/plan':
            board=params.get('board','power');self.send_json({'common':runner.PLANS['common'],**runner.PLANS['boards'].get(board,{})})
        else:self.send_json({'error':'not found'},404)
    def do_POST(self):
        length=int(self.headers.get('Content-Length') or 0);payload=json.loads(self.rfile.read(length) or b'{}')
        try:
            if self.path=='/api/start':self.send_json({'run_id':SESSION.start(payload)})
            elif self.path=='/api/answer':self.send_json({'accepted':bool(SESSION.op and SESSION.op.answer(int(payload.get('id',0)),payload.get('value')))})
            elif self.path=='/api/abort':
                if SESSION.op and SESSION.active():SESSION.op.abort()
                self.send_json({'ok':True})
            else:self.send_json({'error':'not found'},404)
        except Exception as e:self.send_json({'error':str(e)},400)

PAGE=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vinyl ADC · AD3 bench control</title>
<style>
:root{color-scheme:dark;--bg:#0d1711;--card:#132920;--line:#2e4a3b;--text:#e6efe8;--muted:#9db3a5;--accent:#c1ed8f;--pass:#7fe0a0;--fail:#ff7772;--warn:#f6d660;--blue:#75b6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 system-ui,sans-serif}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;padding:16px 22px;border-bottom:1px solid var(--line)}header h1{font-size:20px;margin:0}header small{color:var(--muted)}
main{display:grid;gap:18px;padding:18px 22px;max-width:1300px;margin:0 auto;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr)}@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}.card h2{margin:0 0 10px;font-size:17px}.eyebrow{font-size:12px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin:0 0 6px}
label{display:block;margin:10px 0 4px}select,input[type=text],input[type=number]{width:100%;padding:10px;border-radius:8px;border:1px solid var(--line);background:#0b1510;color:var(--text);font-size:16px}
.radios{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.radios label{margin:0;border:1px solid var(--line);border-radius:8px;padding:10px;text-align:center;cursor:pointer}.radios input{display:none}.radios input:checked+span{color:var(--accent);font-weight:700}.radios label:has(input:checked){border-color:var(--accent);background:#17311f}
button{font:inherit;border:0;border-radius:10px;padding:12px 18px;cursor:pointer;background:#27503a;color:var(--text)}button.primary{background:var(--accent);color:#0d1711;font-weight:700}button.big{font-size:28px;padding:22px;width:100%;letter-spacing:.06em}button.danger{background:#5a2323;color:#ffd9d6}button:disabled{opacity:.45;cursor:not-allowed}
.muted{color:var(--muted)}.warn{border-left:4px solid var(--warn);padding:10px 12px;background:#20240f;border-radius:8px;margin:10px 0}.prompt{border:2px solid var(--accent);border-radius:12px;padding:16px;margin-top:10px}.prompt p{font-size:18px;margin:0 0 14px}
table{width:100%;border-collapse:collapse;margin:8px 0}td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);font-size:15px}th{color:var(--muted);font-weight:600}
.log{max-height:60vh;overflow:auto;font:14px/1.4 ui-monospace,monospace;white-space:pre-wrap}.log div{padding:2px 0;border-bottom:1px dotted #1f3328}.pass{color:var(--pass)}.fail{color:var(--fail);font-weight:700}.carried{color:var(--blue)}.ans{color:var(--warn)}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:13px;background:#1f3328}.pill.PASS{background:#1c4a2d;color:var(--pass)}.pill.FAIL,.pill.ERROR{background:#4a1c1c;color:var(--fail)}.pill.ABORTED{background:#4a3a1c;color:var(--warn)}.pill.RUNNING{background:#1c3a4a;color:var(--blue)}
.steps{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 12px}
</style>
<header><h1>Vinyl ADC · AD3 bench control</h1><small id="device">Looking for the AD3…</small><small>Local only (127.0.0.1). This page relays your confirmations; it never turns the Korad on or off.</small></header>
<main>
<section class="card" id="setup">
<p class="eyebrow">New run</p>
<div class="radios" id="boards"></div>
<label>Scope probes (scope 1, scope 2)<select id="probe"><option value="10,1" selected>10× on scope 1 · 1× on scope 2 (current BNC fixture)</option><option value="10">10× on both</option><option value="1">1× direct flywires on both</option></select></label>
<label id="v3wrap"><input type="checkbox" id="ad3_3v3" checked> +3.3 V from AD3 V+ to digital J2.3 (never together with another 3.3 V source)</label>
<label>Continue from an earlier run of this board<select id="resume"><option value="">No — full run</option></select></label>
<p class="muted" id="resumenote"></p>
<div class="warn">Before you press Start: close WaveForms, disconnect every AD3 lead from the boards, Korad off.</div>
<button class="primary big" id="start">Start</button>
<p class="muted" id="starterr"></p>
</section>
<section class="card" id="live" hidden>
<p class="eyebrow">Current run</p><h2 id="runtitle"></h2><div class="steps" id="steps"></div>
<div id="stepcard"></div>
<div id="promptcard"></div>
<p><button class="danger" id="abort">Abort run</button> <span class="muted">Aborting stops at the next prompt and shuts down AD3 outputs. You still switch the Korad off yourself.</span></p>
<div id="done"></div>
</section>
<section class="card"><p class="eyebrow">Log</p><div class="log" id="log"></div></section>
</main>
<script>
const $=s=>document.querySelector(s);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const BOARDS=[['power','Power'],['digital','Digital'],['stack','Full stack'],['left','Left channel'],['right','Right channel']];
$('#boards').innerHTML=BOARDS.map(([v,l],i)=>`<label><input type="radio" name="board" value="${v}" ${i===0?'checked':''}><span>${l}</span></label>`).join('');
const board=()=>document.querySelector('input[name=board]:checked').value;
let since=0,lastStep=null,running=false;
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});return r.json()}
async function loadReports(){const b=board();$('#v3wrap').style.display=b==='power'?'none':'block';const list=await api('/api/reports?board='+b);const sel=$('#resume');sel.innerHTML='<option value="">No — full run</option>'+list.filter(r=>r.resumable).map(r=>`<option value="${esc(r.id)}">${esc(new Date(r.started).toLocaleString())} · ${esc(r.status)} · carry ${esc(r.passed.join(', '))}</option>`).join('');$('#resumenote').textContent=list.some(r=>r.resumable)?'Carried steps are copied from the earlier report and not repeated. The fixture (probes, 3.3 V source) must match that run.':'No earlier run of this board has leading passed steps to carry over.';}
document.querySelectorAll('input[name=board]').forEach(r=>r.addEventListener('change',loadReports));loadReports();
api('/api/devices').then(d=>{$('#device').textContent=d.devices&&d.devices.length?`AD3 ${d.devices[0].serial} · SDK ${d.sdk}${d.devices[0].in_use?' · IN USE by another program':''}`:'No AD3 found: '+(d.error||'plug it in and reload');});
$('#start').onclick=async()=>{$('#starterr').textContent='';const r=await api('/api/start',{board:board(),probe:$('#probe').value,ad3_3v3:$('#ad3_3v3').checked&&board()!=='power',resume:$('#resume').value||null});if(r.error){$('#starterr').textContent=r.error;return}since=0;$('#log').innerHTML='';$('#done').innerHTML='';$('#stepcard').innerHTML='';$('#setup').hidden=true;$('#live').hidden=false;};
$('#abort').onclick=async()=>{if(confirm('Abort the run? Remaining checks will not be performed.'))await api('/api/abort',{})};
function renderStep(e){const s=e.step;$('#stepcard').innerHTML=`<h3>${esc(s.title)}</h3><p>${esc(s.instructions)}</p>${e.extra?`<p><strong>${esc(e.extra)}</strong></p>`:''}<table><tr><th>Lead</th><th>Connect to</th><th>Net</th></tr>${s.connections.map(c=>`<tr><td>${esc(c.lead)}</td><td><strong>${esc(c.ref)}.${esc(c.pin)}</strong></td><td>${esc(c.net)}</td></tr>`).join('')}<tr><td>AD3 GND, scope 1 clip, scope 2 clip, Korad black</td><td><strong>board GND</strong></td><td>GND</td></tr></table><p class="muted">Pad positions: <a href="http://localhost:8080/#visual-wiring" target="_blank" rel="noreferrer">visual wiring guide</a>.</p>`;}
function renderPrompt(p){const box=$('#promptcard');if(!p){box.innerHTML='<p class="muted">Measuring… keep everything as it is.</p>';return}
 if(p.kind==='confirm')box.innerHTML=`<div class="prompt"><p>${esc(p.message)}</p><button class="primary big" id="confirm">${esc(p.word)}</button><p class="muted">Press only after you have physically done this.</p></div>`;
 else box.innerHTML=`<div class="prompt"><p>${esc(p.message)}</p><input type="number" id="ma" min="0" step="0.1" placeholder="mA from the Korad display"><p></p><button class="primary big" id="confirm">Record current</button></div>`;
 $('#confirm').onclick=async()=>{const value=p.kind==='confirm'?p.word:$('#ma').value;if(p.kind!=='confirm'&&value==='')return;$('#confirm').disabled=true;await api('/api/answer',{id:p.id,value});};
 if(p.kind!=='confirm')$('#ma').focus();}
let shownPrompt=null;
async function poll(){try{const s=await api('/api/state?since='+since);
 if(s.settings){$('#runtitle').innerHTML=`${esc(s.settings.board)} board · <span class="pill ${esc(s.status)}">${esc(s.status)}</span> <small class="muted">${esc(s.settings.run_id)} · ${esc(s.settings.argv.join(' '))}</small>`;$('#steps').innerHTML=s.steps.map(st=>`<span class="pill ${esc(st.status)}">${esc(st.id)}${st.carried_from?' · carried':''}</span>`).join('');
  if(s.running||s.events.length){$('#setup').hidden=true;$('#live').hidden=false;}}
 for(const e of s.events){since=e.seq;const log=$('#log');const d=document.createElement('div');
  if(e.kind==='text'){d.textContent=e.text;if(e.text.includes('CARRIED'))d.className='carried'}
  else if(e.kind==='metric'){d.className=e.status==='PASS'?'pass':'fail';d.textContent=`${e.status} ${e.name}: ${e.value===null?'invalid':Number(e.value).toPrecision(6)} ${e.unit}${e.min!==null||e.max!==null?` [${e.min??'–'}, ${e.max??'–'}]`:''}`}
  else if(e.kind==='step'){d.textContent='STEP '+e.step.title;renderStep(e)}
  else if(e.kind==='prompt'){d.textContent='PROMPT '+e.message;d.className='muted'}
  else if(e.kind==='answer'){d.textContent='→ '+e.text;d.className='ans'}
  else if(e.kind==='finished'){d.textContent=e.status+(e.error?': '+e.error:'');d.className=e.status==='PASS'?'pass':'fail';$('#done').innerHTML=`<div class="warn"><strong>${esc(e.status)}</strong> ${esc(e.error||'Finished screening sequence.')}<br>Switch the Korad OFF now. Report: <code>assembly/bench/results/${esc(e.id)}/report.json</code></div><button class="primary" id="again">New run</button>`;$('#again').onclick=()=>{$('#live').hidden=true;$('#setup').hidden=false;loadReports()};}
  log.appendChild(d);log.scrollTop=log.scrollHeight;}
 const key=s.pending?s.pending.id:null;if(key!==shownPrompt){shownPrompt=key;renderPrompt(s.running?s.pending:null)}
 if(!s.running&&s.settings&&!$('#done').innerHTML)$('#promptcard').innerHTML='';
 }catch(err){console.error(err)}setTimeout(poll,400)}
poll();
</script></html>'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8090);a=p.parse_args()
    (runner.HERE/'results').mkdir(exist_ok=True)
    print(f'AD3 bench control: http://127.0.0.1:{a.port}  (Ctrl+C stops the server; an active run is aborted at its next prompt)',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
