#!/usr/bin/env python3
"""Vinyl ripper: records what the Vinyl ADC hears, splits it into tracks and hands finished albums to Jellyfin.

    python3 ripper.py                      # on the Pi; dashboard on http://vinyladc.local:8091
    python3 ripper.py --replay x.raw --fast --home /tmp/vinyl   # offline test with a saved capture

Flow: the needle drops -> the level rises -> a *side* is recorded to disk (with a few seconds of pre-roll) ->
the needle lifts -> the side is closed. If an album is selected in the dashboard (MusicBrainz search), the
side is matched to the next tracks of that album by duration, cut at the quiet gaps nearest the expected
boundaries, and when the album is complete (or on request) every track is normalised with one common gain,
encoded to 24-bit FLAC, tagged, given cover art and published in the outbox. A small puller on the media
server fetches the outbox and drops the album into the Jellyfin music library.

The audio path is: I2S words -> the two 1-bit modulator streams -> repair of stuck runs (a hardware fault
marker, never produced by music) -> CIC + FIR decimation to 48 kHz (decimate.py) -> DC removal.
Needs NumPy; `flac` and python3-mutagen for encoding and tagging.
"""
import argparse,collections,hashlib,json,queue,re,shutil,signal,subprocess,threading,time,urllib.error,urllib.parse,urllib.request
from collections import deque
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import numpy as np
import decimate as d

FS=48000;BLOCK_FRAMES=24000;BLOCK_BYTES=BLOCK_FRAMES*8;CHUNK=4800           # 0.5 s blocks, 100 ms level chunks
UA='VinylADC-Ripper/0.1 ( https://github.com/MadsRudolph/vinyl-adc )'
DEFAULTS={'start_db':-62.,'start_seconds':2.,'stop_db':-65.,'stop_seconds':30.,'preroll_seconds':2.5,'min_side_seconds':90.,'max_side_seconds':2400.,
          'gap_db':-63.,'gap_seconds':1.2,'snap_seconds':15.,'channel_mode':'auto','repair_stuck_runs':True,'target_peak_dbfs':-1.,'max_gain_db':24.,
          'identify':True,'identify_at_seconds':480.,'finalize_after_hours':3.,'min_free_gb':3.}
ACOUSTID='https://api.acoustid.org/v2/lookup'

def db(x):return float(10*np.log10(x+1e-20))
def safe(name):return re.sub(r'\s+',' ',re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',name)).strip(' .') or 'Unknown'

# ------------------------------------------------------------------ signal path
class Dsp:
    def __init__(self,cfg):
        self.cfg=cfg;h=d.compensating_fir();self.chain=[(d.Cic(),d.FirDecimator(h)) for _ in range(2)];self.dc=[None,None];self.last=[0.,0.];self.repaired=0
    def process(self,raw):
        words=np.frombuffer(raw,dtype='<u4').reshape(-1,2);out=[];health=[]
        for i,bits in enumerate(d.split_bits(words)):
            b=bits.view(np.int8);chg=np.flatnonzero(np.diff(b)!=0);mean_run=len(b)/(len(chg)+1);density=float(b.mean())
            if self.cfg['repair_stuck_runs'] and len(chg):
                starts=np.r_[0,chg+1];lens=np.diff(np.r_[starts,len(b)]);bad=np.flatnonzero(lens>=7)
                if 0<len(bad)<100:                      # a healthy loop never holds a level for 7 clocks; a broken one does it constantly
                    b=b.copy()
                    for k in bad:
                        s,n=starts[k],lens[k];b[s:s+n]=((1-b[s-1] if s else 0)+np.arange(n))%2
                    self.repaired+=len(bad)
            cic,fir=self.chain[i];y=fir.process(cic.process(b*2-1))
            m=float(y.mean());self.dc[i]=m if self.dc[i] is None else .9*self.dc[i]+.1*m
            out.append(y-self.dc[i])
            ok=.02<density<.98 and mean_run<4
            health.append({'ok':ok,'density':density,'mean_run':float(mean_run),'dc':self.dc[i],'verdict':'Healthy' if ok else ('Stuck bitstream' if not .02<density<.98 else 'Loop oscillating')})
        mode=self.cfg['channel_mode']
        if mode=='auto':mode='stereo' if health[0]['ok']==health[1]['ok'] else ('left' if health[0]['ok'] else 'right')
        if mode=='left':out[1]=out[0]
        elif mode=='right':out[0]=out[1]
        audio=np.vstack(out);n=audio.shape[1]//CHUNK;seg=audio[:,:n*CHUNK].reshape(2,n,CHUNK)
        diff=np.diff(np.concatenate((np.array(self.last)[:,None],audio),axis=1),axis=1)[:,:n*CHUNK].reshape(2,n,CHUNK);self.last=[float(audio[0,-1]),float(audio[1,-1])]
        level=10*np.log10((diff**2).mean(axis=2).max(axis=0)+1e-20)   # treble-weighted: ignores mains hum, follows music and groove noise
        return audio,{'mode':mode,'health':health,'level':level,'peaks':np.abs(seg).max(axis=2).T,
                      'rms_db':[db(float((a**2).mean())) for a in audio],'peak_db':[db(float(np.abs(a).max())**2) for a in audio]}

# ------------------------------------------------------------------ MusicBrainz
MB_LOCK=threading.Lock();MB_LAST=[0.]
def http_get(url,accept='application/json'):
    """MusicBrainz and the Cover Art Archive allow about one request per second per address and answer 503 when that is exceeded:
    space the requests, retry a few times, and let a real failure surface as an error instead of as 'nothing found'."""
    with MB_LOCK:
        for attempt in range(4):
            wait=1.1-(time.time()-MB_LAST[0])
            if wait>0:time.sleep(wait)
            MB_LAST[0]=time.time()
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA,'Accept':accept}),timeout=25) as r:return r.read()
            except urllib.error.HTTPError as e:
                if e.code not in (429,503) or attempt==3:raise
                time.sleep(2*(attempt+1))
def http_json(url):return json.loads(http_get(url))
def mb_search(q):
    data=http_json('https://musicbrainz.org/ws/2/release/?fmt=json&limit=25&dismax=true&query='+urllib.parse.quote(q));out=[]   # dismax: free text across artist, title and more
    for r in data.get('releases',[]):
        out.append({'mbid':r['id'],'title':r.get('title',''),'artist':''.join(a.get('name','')+a.get('joinphrase','') for a in r.get('artist-credit',[])),'date':r.get('date',''),
                    'country':r.get('country',''),'tracks':r.get('track-count'),'score':r.get('score',0),'label':', '.join(sorted({(l.get('label') or {}).get('name','') for l in r.get('label-info',[])}-{''})),
                    'formats':', '.join(f"{n}× {f}" if n>1 else f for f,n in sorted(collections.Counter(m.get('format') or '?' for m in r.get('media',[])).items()))})
    words=set(re.findall(r'\w+',q.lower()))
    for r in out:r['rank']=r['score']+(15 if set(re.findall(r'\w+',r['artist'].lower()))<=words else 0)      # the artist typed in full outranks tribute albums
    out.sort(key=lambda r:(-r['rank'],'Vinyl' not in r['formats']));return out
def mb_release(mbid):
    r=http_json(f'https://musicbrainz.org/ws/2/release/{mbid}?fmt=json&inc=recordings+artist-credits+media');tracks=[]
    for m in r.get('media',[]):
        for t in m.get('tracks',[]):
            length=t.get('length') or (t.get('recording') or {}).get('length')
            tracks.append({'disc':m.get('position',1),'position':t.get('position'),'number':t.get('number',''),'title':t.get('title',''),'length':length/1000. if length else None,
                           'recording':(t.get('recording') or {}).get('id'),'artist':''.join(a.get('name','')+a.get('joinphrase','') for a in t.get('artist-credit',[]))})
    return {'mbid':mbid,'title':r.get('title',''),'artist':''.join(a.get('name','')+a.get('joinphrase','') for a in r.get('artist-credit',[])),'date':r.get('date',''),
            'discs':len(r.get('media',[])),'tracks':tracks}

def fingerprint(path,start,seconds=120.):
    """Chromaprint of `seconds` of a raw 24-bit side file from `start` seconds in (fpcalc from libchromaprint-tools)."""
    a=int(start*FS)*6;raw=np.memmap(path,dtype=np.uint8,mode='r')[a:a+int(seconds*FS)*6]
    if len(raw)<FS*6*30:raise ValueError('too little audio to fingerprint')
    out=subprocess.run(['fpcalc','-format','s24le','-rate',str(FS),'-channels','2','-length',str(int(seconds)),'-json','-'],input=bytes(raw),capture_output=True,check=True).stdout
    return json.loads(out)['fingerprint'],len(raw)//(6*FS)
def acoustid_lookup(key,fp,duration):
    body=urllib.parse.urlencode({'client':key,'duration':int(duration),'fingerprint':fp,'meta':'recordings releases tracks'}).encode()
    with MB_LOCK:
        req=urllib.request.Request(ACOUSTID,data=body,headers={'User-Agent':UA,'Content-Type':'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read())
def rank_releases(results,current=None,min_score=.5):
    """Every (release, medium, track) an AcoustID match could be, best first: the album already in use, then vinyl pressings, then the match score."""
    found=[]
    for res in results:
        if res.get('score',0)<min_score:continue
        for rec in res.get('recordings') or []:
            artist=''.join(a.get('name','')+a.get('joinphrase','') for a in rec.get('artists') or [])
            for rel in rec.get('releases') or []:
                for med in rel.get('mediums') or []:
                    for tr in med.get('tracks') or []:
                        vinyl='vinyl' in (med.get('format') or '').lower()
                        found.append({'score':res['score']+(100 if rel['id']==current else 0)+(2 if vinyl else 0)-(med.get('track_count') or 0)/100,
                                      'release':rel['id'],'album':rel.get('title',''),'medium':med.get('position',1),'position':tr.get('position'),
                                      'recording':rec['id'],'title':rec.get('title',''),'artist':artist,'vinyl':vinyl})
    return sorted(found,key=lambda x:-x['score'])

# ------------------------------------------------------------------ the ripper
class Ripper:
    def __init__(self,home,replay=None,fast=False):
        self.home=Path(home).expanduser();(self.home/'sides').mkdir(parents=True,exist_ok=True);(self.home/'library').mkdir(exist_ok=True)
        self.replay,self.fast=replay,fast;self.lock=threading.RLock();self.jobs=queue.Queue();self.state_path=self.home/'state.json'
        self.store={'config':dict(DEFAULTS),'albums':{},'sides':[],'current_album':None}
        if self.state_path.exists():
            saved=json.loads(self.state_path.read_text());self.store.update(saved);self.store['config']={**DEFAULTS,**saved.get('config',{})}
        self.cfg=self.store['config'];self.dsp=Dsp(self.cfg)
        self.status='starting';self.message='Starting…';self.meters=None;self.recent=deque(maxlen=600)       # 60 s of (peakL,peakR,level)
        self.stop=threading.Event();self.recover_orphans()
        self.acoustid=(self.home/'acoustid.key').read_text().strip() if (self.home/'acoustid.key').exists() else None
        self.ring=deque(maxlen=120);self.hold_until=0.;self.last_check=time.time()       # ring: the last 60 s of decimated audio, for measurements
        self.pre=deque();self.side=None;self.loud=deque(maxlen=int(self.cfg['start_seconds']*10));self.still=deque(maxlen=int(self.cfg['stop_seconds']*10));self.quiet=0.;self.gap_run=0;self.events=deque(maxlen=40);self.seq=0;self.manual=None
    def recover_orphans(self):
        """A side file without a state entry means the process died while recording (power loss, kill). Rebuild its envelope and keep it."""
        known={Path(x['file']).name for x in self.store['sides']}
        for f in sorted((self.home/'sides').glob('*.s24')):
            if f.name in known or f.stat().st_size<6*FS*10:continue
            raw=np.memmap(f,dtype=np.uint8,mode='r');frames=len(raw)//6;peaks=[];level=[];last=np.zeros(2)
            for a in range(0,frames-CHUNK+1,CHUNK*100):
                u=np.asarray(raw[a*6:min(frames,a+CHUNK*100)*6]).reshape(-1,3).astype(np.int32);x=(u[:,0]|(u[:,1]<<8)|(u[:,2]<<16));x=(np.where(x>=1<<23,x-(1<<24),x)/2**23).reshape(-1,2)
                n=len(x)//CHUNK;seg=x[:n*CHUNK].reshape(n,CHUNK,2);dx=np.diff(np.vstack((last,x[:n*CHUNK])),axis=0).reshape(n,CHUNK,2);last=x[n*CHUNK-1]
                peaks+=[(float(p[0]),float(p[1])) for p in np.abs(seg).max(axis=1)];level+=[float(v) for v in 10*np.log10((dx**2).mean(axis=1).max(axis=1)+1e-20)]
            gaps=[];run=0
            for i,v in enumerate(level):
                if v<self.store['config']['gap_db']:run+=1
                else:
                    if run*.1>=self.store['config']['gap_seconds']:gaps.append([round((i-run)*.1,1),round(i*.1,1)])
                    run=0
            np.save(f.with_suffix('.env.npy'),np.column_stack((np.array(peaks),np.array(level))))
            sid=f.stem;started=time.mktime(time.strptime(sid,'%Y%m%d-%H%M%S')) if re.fullmatch(r'\d{8}-\d{6}',sid) else f.stat().st_mtime
            self.store['sides'].append({'id':sid,'started':started,'file':str(f),'frames':frames,'gaps':gaps,'album':None,'status':'recorded','seconds':round(frames/FS,1),'peak':float(np.max(peaks)) if peaks else 0.,'tracks':[],'recovered':True})
            print(f'Recovered an interrupted recording: {sid}, {frames/FS/60:.1f} min',flush=True)
        self.store['sides'].sort(key=lambda x:x['started'])
    # ---- persistence and logging
    def save(self):
        with self.lock:tmp=self.state_path.with_suffix('.tmp');tmp.write_text(json.dumps(self.store,indent=1));tmp.replace(self.state_path)
    def log(self,text):
        with self.lock:self.events.appendleft({'time':time.time(),'text':text})
        print(time.strftime('%H:%M:%S'),text,flush=True)
    # ---- capture
    def source(self):
        if self.replay:
            data=open(self.replay,'rb').read();data=data[:len(data)//BLOCK_BYTES*BLOCK_BYTES]
            for i in range(0,len(data),BLOCK_BYTES):
                yield data[i:i+BLOCK_BYTES]
                if not self.fast:time.sleep(.5)
            return
        while True:
            p=subprocess.Popen(['arecord','-q','-D','hw:CARD=vinyladc','-c','2','-r','48000','-f','S32_LE','-t','raw','--buffer-time=2000000','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                while True:
                    raw=p.stdout.read(BLOCK_BYTES)
                    if len(raw)<BLOCK_BYTES:break
                    yield raw
            finally:p.kill()
            err=p.stderr.read().decode(errors='replace').strip().splitlines()
            with self.lock:self.status='waiting';self.message='No clocks from the ADC. Is the stack powered? '+(err[-1] if err else '')
            if self.side:self.close_side('the ADC stopped clocking')
            time.sleep(2)
    def capture_loop(self):
        q=queue.Queue(maxsize=60)
        def reader():
            for raw in self.source():q.put(raw)
            q.put(None)
        threading.Thread(target=reader,daemon=True).start()
        while True:
            try:raw=q.get(timeout=.5)
            except queue.Empty:raw=b''
            if self.stop.is_set():
                if self.side:self.close_side('the ripper is shutting down',keep=True)
                self.jobs.join();self.save();return
            if raw==b'':continue
            if raw is None:
                if self.side:self.close_side('end of the replay file')
                self.jobs.join();self.log('Replay finished');return
            t0=time.time();audio,info=self.dsp.process(raw);self.feed(audio,info);self.ring.append(audio.astype(np.float32))
            if time.time()-self.last_check>60:self.last_check=time.time();self.housekeeping()
            with self.lock:
                self.seq+=1;self.status='recording' if self.side else 'idle';self.message='';self.meters={**{k:info[k] for k in ('mode','health','rms_db','peak_db')},'level_db':float(info['level'].max()),
                    'cpu_ms':round((time.time()-t0)*1000),'backlog':q.qsize(),'repaired':self.dsp.repaired}
                for pk,lv in zip(info['peaks'],info['level']):self.recent.append((float(pk[0]),float(pk[1]),float(lv)))
    # ---- recorder state machine, fed every 0.5 s
    def feed(self,audio,info):
        cfg=self.cfg;pcm=np.clip(np.round(audio.T*(2**23-1)),-2**23,2**23-1).astype('<i4').reshape(-1,1).view(np.uint8).reshape(-1,4)[:,:3].tobytes()
        block=(pcm,[(float(p[0]),float(p[1])) for p in info['peaks']],[float(v) for v in info['level']])
        if self.side is None:
            self.pre.append(block)
            while len(self.pre)>max(1,round(cfg['preroll_seconds']*2)):self.pre.popleft()
            self.loud.extend(v>cfg['start_db'] for v in block[2])
            if self.manual=='start' or (time.time()>self.hold_until and len(self.loud)==self.loud.maxlen and sum(self.loud)>=.7*len(self.loud)):self.open_side()
            self.manual=None;return
        self.write_block(block)
        for v in block[2]:
            self.still.append(v<cfg['stop_db'])     # a window, not a run: isolated clicks must not keep a finished side open
            t=len(self.side['level'])*.1
            if v<cfg['gap_db']:self.gap_run+=1
            else:
                if self.gap_run*.1>=cfg['gap_seconds']:
                    g0=t-self.gap_run*.1;self.side['gaps'].append([round(g0,1),round(t,1)])
                    ident=self.side.get('ident') or {}
                    if ident.get('status') in (None,'unknown') and ident.get('tries',0)<4 and g0-self.side.get('ident_from',.5)>40:   # a track has ended: its length is known, identify now; retry on later tracks (intros are rarely fingerprinted)
                        self.side['ident']={'status':'pending','tries':ident.get('tries',0)+1};self.jobs.put(('identify',(self.side['id'],(self.side.get('ident_from',.5),(g0,t)))))
                    if self.side.get('ident_from',.5)<g0-40:self.side['ident_from']=t
                self.gap_run=0
        seconds=self.side['frames']/FS
        if seconds>=self.cfg['identify_at_seconds'] and not self.side.get('ident'):                       # tracks that run into each other: scan durations
            self.side['ident']={'status':'pending'};self.jobs.put(('identify',(self.side['id'],None)))
        if self.manual=='stop':self.close_side('stopped from the dashboard')
        elif len(self.still)==self.still.maxlen and sum(self.still)>=.8*len(self.still):self.quiet=cfg['stop_seconds'];self.close_side(f'{cfg["stop_seconds"]:.0f} s of silence')
        elif seconds>=cfg['max_side_seconds']:self.close_side('maximum side length reached')
        self.manual=None
    def open_side(self):
        sid=time.strftime('%Y%m%d-%H%M%S');path=self.home/'sides'/f'{sid}.s24'
        self.side={'id':sid,'started':time.time(),'file':str(path),'frames':0,'peaks':[],'level':[],'gaps':[],'album':self.store['current_album'],'status':'recording','fh':open(path,'wb')}
        for block in self.pre:self.write_block(block)
        self.pre.clear();self.loud.clear();self.still.clear();self.quiet=0.;self.gap_run=0;self.log(f'Recording started ({sid})')
    def write_block(self,block):
        pcm,peaks,level=block;s=self.side;s['fh'].write(pcm);s['frames']+=len(pcm)//6;s['peaks']+=peaks;s['level']+=level
    def close_side(self,why,keep=False):
        s=self.side;self.side=None;s['fh'].close();s.pop('fh');seconds=s['frames']/FS;music=seconds-self.quiet;self.quiet=0.
        if music<self.cfg['min_side_seconds'] and not keep:
            Path(s['file']).unlink(missing_ok=True);self.log(f'Discarded a {music:.0f} s recording ({why}); shorter than {self.cfg["min_side_seconds"]:.0f} s');return
        np.save(Path(s['file']).with_suffix('.env.npy'),np.column_stack((np.array(s['peaks']),np.array(s['level']))))
        meta={k:s[k] for k in ('id','started','file','frames','gaps','album')};meta.update(status='recorded',seconds=round(seconds,1),peak=float(np.max(s['peaks'])),tracks=[],first=s.get('first'),anchor=s.get('anchor'),ident=s.get('ident'))
        with self.lock:self.store['sides'].append(meta);self.save()
        self.log(f'Side {s["id"]} closed after {seconds/60:.1f} min ({why})')
        if (meta['ident'] or {}).get('status') in (None,'pending','unknown','failed'):meta['ident']={'status':'pending'};self.jobs.put(('identify',(meta['id'],'closed')))
        self.jobs.put(('split',meta['id']));self.jobs.put(('purge',None))
    # ---- track assignment
    def side_env(self,side):return np.load(Path(side['file']).with_suffix('.env.npy'))
    def split_side(self,arg):
        sid,first=arg if isinstance(arg,tuple) else (arg,None)
        with self.lock:
            side=next(s for s in self.store['sides'] if s['id']==sid);album=self.store['albums'].get(side['album'] or '')
        if not album:self.log(f'Side {sid} waits for an album: search for the record in the dashboard and assign it');return
        env=self.side_env(side);level=env[:,2];frac=lambda mask,n:np.convolve(mask.astype(float),np.ones(n)/n,'same')
        music=np.flatnonzero(frac(level>self.cfg['start_db'],30)>=.5)      # windows, not single frames: one click in the run-out must not count as music
        if not len(music):return
        # a fade-out sinks below the start threshold long before it is over: extend both ends to where the groove is really silent
        silent=frac(level<self.cfg['stop_db'],30)>=.8;a,b=int(music[0]),int(music[-1])
        while a>0 and not silent[a]:a-=1
        while b<len(level)-1 and not silent[b]:b+=1
        t0=float(max(0.,a*.1-.5));t1=float(min(side['seconds'],b*.1+3.));T=t1-t0
        # gaps from the finished envelope, merged across the clicks that fragment them while recording
        edge=np.diff(np.r_[0,(frac(level<self.cfg['gap_db'],15)>=.8).astype(int),0]);found=[]
        for g0,g1 in zip(np.flatnonzero(edge==1)*.1,np.flatnonzero(edge==-1)*.1):
            if found and g0-found[-1][1]<2.5:found[-1][1]=round(float(g1),1)
            else:found.append([round(float(g0),1),round(float(g1),1)])
        side['gaps']=[g for g in found if g[1]-g[0]>=self.cfg['gap_seconds'] and t0+20<(g[0]+g[1])/2<t1-20]
        def fit(lengths,span):
            """How many tracks of these lengths fill `span` seconds, and where their boundaries fall (scaled to fit); gaps stand in when lengths are unknown."""
            if lengths and all(lengths):
                sums=np.cumsum(lengths);k=max(1,int(np.sum(sums<=span+20)))                        # complete tracks
                if k<len(lengths) and span-sums[k-1]>45:return k+1,[float(v) for v in sums[:k]],-1.  # plus one the needle was lifted from (err -1 marks it partial)
                return k,[float(v)*span/sums[k-1] for v in sums[:k-1]],float(abs(sums[k-1]-span))
            return min(len(lengths),1),[],0.
        def snap(e):
            near=[g for g in side['gaps'] if abs((g[0]+g[1])/2-e)<=self.cfg['snap_seconds']]
            if near:return float(np.mean(max(near,key=lambda g:g[1]-g[0])))
            lo,hi=int(max(0,e-self.cfg['snap_seconds'])*10),int((e+self.cfg['snap_seconds'])*10);smooth=np.convolve(level[lo:hi],np.ones(10)/10,'valid')   # tracks that run into each other: the quietest second nearby
            return (lo+int(np.argmin(smooth))+5)*.1 if len(smooth) else e
        anchor=side.get('anchor') if first is None and side.get('first') is None else None
        if anchor and anchor['time']-t0>=30:            # the fingerprint named the track that starts at anchor['time']; whatever came before it are the tracks just ahead of it
            ta=snap(anchor['time']) if any(abs((g[0]+g[1])/2-anchor['time'])<=5 for g in side['gaps']) else float(anchor['time']);hit=int(anchor['index'])
            m,back,err=fit([album['tracks'][i]['length'] for i in range(hit-1,-1,-1)],ta-t0);first=hit-m;partial=set()
            if err>max(45.,.08*(ta-t0)) or err<0:partial.add(first);self.log(f'Side {sid}: the {(ta-t0)/60:.1f} min before “{album["tracks"][hit]["title"]}” is not a whole track (needle dropped mid-track); it will not be kept')
            before=[snap(ta-v) for v in reversed(back)];rest=album['tracks'][hit:];k,fwd,err=fit([x['length'] for x in rest],t1-ta);after=[snap(ta+v) for v in fwd]
            if not rest:self.log(f'Album already complete; side {sid} left unassigned');return
            cuts=before+[ta]+after;k=m+k
        else:
            if first is None:first=anchor['index'] if anchor else side['first'] if side.get('first') is not None else album['next_track']
            first=int(first);rest=album['tracks'][first:]
            if not rest:self.log(f'Album already complete; side {sid} left unassigned');return
            k,fwd,err=fit([x['length'] for x in rest],T);partial=set()
            if err>max(45.,.08*T):self.log(f'Side {sid}: recorded {T/60:.1f} min, which does not match a whole number of tracks; check the album choice')
            if not all(x['length'] for x in rest):gaps=[g for g in side['gaps'] if t0+20<(g[0]+g[1])/2<t1-20];k=min(len(gaps)+1,len(rest));fwd=[(g[0]+g[1])/2-t0 for g in gaps[:k-1]]
            cuts=[snap(t0+v) for v in fwd]
        if err<0:partial.add(first+k-1);self.log(f'Side {sid}: the needle was lifted during “{album["tracks"][first+k-1]["title"]}”; that track will not be kept')
        edges=[t0]+cuts+[t1];tracks=[{'index':first+i,'start':round(edges[i],2),'end':round(edges[i+1],2),'snapped':i==0 or any(abs(edges[i]-(g[0]+g[1])/2)<.01 for g in side['gaps']),'partial':first+i in partial} for i in range(k)]
        with self.lock:
            have={tr['index'] for s in self.store['sides'] if s is not side and s['album']==album['mbid'] for tr in s['tracks'] if not tr.get('partial')}
            if all(tr['index'] in have for tr in tracks if not tr.get('partial')):          # the same side played again: the library already has it
                self.log(f'Side {sid} is tracks {first+1}–{first+k} of “{album["title"]}” again; already recorded, so it goes to the trash');self.trash_side(side);return
            mine={tr['index'] for tr in tracks if not tr.get('partial')}
            for other in self.store['sides']:                       # a fresh play of tracks an earlier, shorter side had (a restart from track 1): the new side wins them
                if other is not side and other['album']==album['mbid'] and any(tr['index'] in mine for tr in other['tracks']):
                    other['tracks']=[tr for tr in other['tracks'] if tr['index'] not in mine];self.log(f'Side {other["id"]} loses its overlap with {sid}')
                    if not other['tracks']:self.log(f'Side {other["id"]} is fully replaced and goes to the trash');self.trash_side(other)
            side['tracks']=tracks;side['status']='split';self.recount(album);self.save()
        self.log(f'Side {sid}: tracks {first+1}–{first+k} of “{album["title"]}”'+(' — album complete' if album['status']=='complete' else ''))
        if album['status']=='complete':self.jobs.put(('finalize',album['mbid']))
    def find_side(self,sid):
        with self.lock:
            if self.side and self.side['id']==sid:return self.side
            return next((s for s in self.store['sides'] if s['id']==sid),None)
    def track_segments(self,side,limit=4):
        """From a closed side's envelope: the first few tracks as (start, quiet fragments at their end). Fragments within 30 s of
        each other belong to one track end (a fade-out leaves several); the true length ends somewhere in that cluster."""
        level=self.side_env(side)[:,2];frac=lambda mask,n:np.convolve(mask.astype(float),np.ones(n)/n,'same')
        music=np.flatnonzero(frac(level>self.cfg['start_db'],30)>=.5)
        if not len(music):return []
        t0=max(0.,music[0]*.1-.5);t1=music[-1]*.1+1.;edge=np.diff(np.r_[0,(frac(level<self.cfg['gap_db'],15)>=.8).astype(int),0])
        gaps=[(a*.1,b*.1) for a,b in zip(np.flatnonzero(edge==1),np.flatnonzero(edge==-1)) if b-a>=5];segments=[];start=t0
        while len(segments)<limit:
            cluster=[g for g in gaps if g[0]>start+40];cluster=[g for g in cluster if g[0]<=cluster[0][0]+30] if cluster else []
            if not cluster:
                if t1-start>40 and not segments:segments.append((start,[(t1,t1)]))
                break
            segments.append((start,sorted(cluster,key=lambda g:g[0]-g[1])));start=max(g[1] for g in cluster)
        return segments
    def identify(self,arg):
        """Fingerprint the first two minutes of a side and ask AcoustID which recording it is; that fixes the album and the starting track.

        AcoustID only answers when the declared duration is within about ten seconds of the real track length, so the
        lookup is made once the first track's length is known: from the first gap while recording (`duration`), from the
        finished envelope ('closed'), or by scanning plausible lengths when tracks run into each other (None).
        """
        sid,duration=arg if isinstance(arg,tuple) else (arg,'closed');side=self.find_side(sid)
        if side is None or not self.cfg['identify']:return
        if not self.acoustid:
            side['ident']={'status':'no key'};self.log('Cannot identify the record: no AcoustID key (see ~/vinyl/acoustid.key)');return
        try:
            segments=self.track_segments(side) if duration=='closed' else [duration] if isinstance(duration,tuple) else [None]
            res={};n=0
            for seg in segments:                                    # one track after another until something is known (intros are rarely fingerprinted)
                if seg is None:start,candidates=.5,list(range(120,int(side['frames']/FS)+1,10))
                else:                                               # (track start, quiet fragments): the track ends where the next begins, somewhere in or after the gap
                    start,gaps=seg;gaps=gaps if isinstance(gaps,list) else [gaps];candidates=[]
                    for g0,g1 in gaps:candidates+=[(g0+g1)/2-start,g1-start,g0-start]
                    candidates+=[c+d for c in candidates[:3] for d in (10,-10)]
                    seen=[];candidates=[c for c in candidates if c>=30 and not any(abs(c-x)<3 for x in seen) and not seen.append(c)][:8]
                if not candidates:continue
                fp,_=fingerprint(side['file'],start,min(120.,max(30.,candidates[0])));matched_start=start
                for d in candidates:
                    if n:time.sleep(.4)                               # AcoustID allows three requests a second
                    res=acoustid_lookup(self.acoustid,fp,d);n+=1
                    if res.get('results'):break
                if res.get('results'):break
        except Exception as e:side['ident']={'status':'failed','error':repr(e)};self.log(f'Identification failed: {e!r}');return
        start=matched_start if res.get('results') else .5
        with self.lock:current=self.store['albums'].get(side['album'] or self.store['current_album'] or '')
        matches=rank_releases(res.get('results',[]),current['mbid'] if current else None)
        if not matches:side['ident']={'status':'unknown','tries':(side.get('ident') or {}).get('tries',1)};self.log('AcoustID does not know this track; trying again after the next one' if self.side is side else 'AcoustID does not know this record; choose the album in the dashboard');return
        # the album in use wins whenever one of its recordings matched, even if AcoustID lists that recording under other pressings only
        recs={m['recording'] for m in matches};hit=next((i for i,t in enumerate(current['tracks']) if t['recording'] in recs),None) if current else None
        if hit is not None:best=next(m for m in matches if m['recording']==current['tracks'][hit]['recording'])
        else:
            best=matches[0]
            if current and current.get('status')=='in progress':self.jobs.put(('finalize',current['mbid']))   # a new record: send what the last one has
            try:album=mb_release(best['release']);album.update(next_track=0,status='selected')
            except Exception as e:side['ident']={'status':'failed','error':repr(e)};self.log(f'MusicBrainz lookup failed: {e!r}');return
            with self.lock:self.store['albums'].setdefault(album['mbid'],album);current=self.store['albums'][album['mbid']];self.store['current_album']=album['mbid']
            self.log(f'Record identified: {current["artist"]} — {current["title"]}'+('' if best['vinyl'] else ' (no vinyl pressing matched; using another edition)'))
            hit=next((i for i,t in enumerate(current['tracks']) if t['recording']==best['recording']),None)
            if hit is None:hit=next((i for i,t in enumerate(current['tracks']) if t['disc']==best['medium'] and t['position']==best['position']),0)
        with self.lock:
            side['album']=current['mbid'];side['anchor']={'time':float(start),'index':hit};side['first']=None;side['ident']={'status':'ok','title':best['title'],'artist':best['artist'],'score':round(best['score']%100,2)};self.save()
        self.log(f'Side {sid}: track {hit+1}, {best["title"]}, starts {start/60:.1f} min in')
    def housekeeping(self):
        """An album nobody has added to for a few hours is sent as it is: one side of a record still ends up in the library."""
        with self.lock:
            for a in list(self.store['albums'].values()):
                if a.get('status')!='in progress':continue
                last=max((s['started']+s['seconds'] for s in self.store['sides'] if s['album']==a['mbid']),default=0)
                if last and time.time()-last>self.cfg['finalize_after_hours']*3600 and not (self.side and self.side['album']==a['mbid']):
                    self.log(f'“{a["title"]}”: nothing new for {self.cfg["finalize_after_hours"]:g} h, sending what was recorded');self.jobs.put(('finalize',a['mbid']))
    def trash_side(self,side):
        """Nothing is deleted here: the files move to ~/vinyl/trash, which purge() thins out only when the disk runs short."""
        with self.lock:
            old=self.store['albums'].get(side['album'] or '')
            if side in self.store['sides']:self.store['sides'].remove(side)
            if old:self.recount(old)
            self.save()
        trash=self.home/'trash';trash.mkdir(exist_ok=True)
        for f in (Path(side['file']),Path(side['file']).with_suffix('.env.npy')):
            if f.exists():shutil.move(str(f),str(trash/f.name))
    def purge(self,_=None):
        """Keep `min_free_gb` free: oldest first, drop trash, then the raw audio of albums that are already in the library (their entries stay)."""
        def free():return shutil.disk_usage(self.home).free/2**30
        if free()>=self.cfg['min_free_gb']:return
        with self.lock:
            delivered={a['mbid'] for a in self.store['albums'].values() if a.get('status')=='delivered'}
            raw=[s for s in self.store['sides'] if s['album'] in delivered and Path(s['file']).exists()]
        victims=sorted([(f.stat().st_mtime,f) for f in (self.home/'trash').glob('*') if f.is_file()])+sorted([(s['started'],Path(s['file'])) for s in raw])
        for _,f in victims:
            if free()>=self.cfg['min_free_gb']:break
            for g in {f,f.with_suffix('.env.npy'),f.with_suffix('.s24')}:
                if g.exists() and g.parent.name in ('trash','sides'):g.unlink()
            self.log(f'Disk below {self.cfg["min_free_gb"]:g} GB free: removed {f.name}')
        for s in raw:
            if not Path(s['file']).exists():s['purged']=True
        self.save()
    def recount(self,album):
        """What has been recorded decides where the album stands, so assigning, unassigning or re-cutting a side can never leave a stale counter."""
        done={tr['index'] for s in self.store['sides'] if s['album']==album['mbid'] for tr in s['tracks'] if not tr.get('partial')}
        album['next_track']=max(done)+1 if done else 0
        if album.get('status') not in ('encoding','ready','delivered'):album['status']='complete' if len(done)>=len(album['tracks']) else ('in progress' if done else 'selected')
    # ---- encoding
    def finalize(self,mbid):
        import mutagen.flac
        with self.lock:album=self.store['albums'][mbid];sides=[{**s,'tracks':[t for t in s['tracks'] if not t.get('partial')]} for s in self.store['sides'] if s['album']==mbid];sides=[s for s in sides if s['tracks']]
        if not sides:self.log('Nothing recorded for this album yet');return
        with self.lock:album['status']='encoding'
        peak=max(float(self.side_env(s)[int(tr['start']*10):int(tr['end']*10)+1,:2].max()) for s in sides for tr in s['tracks'])
        gain_db=min(self.cfg['max_gain_db'],self.cfg['target_peak_dbfs']-20*np.log10(peak+1e-9));gain=10**(gain_db/20)
        folder=self.home/'library'/safe(album['artist'])/safe(f"{album['title']} ({album['date'][:4]}) [Vinyl]" if album['date'] else f"{album['title']} [Vinyl]");folder.mkdir(parents=True,exist_ok=True)
        cover=self.cover(mbid)
        if cover:(folder/'cover.jpg').write_bytes(cover)
        else:self.log('No cover art found for this release')
        files=[]
        for s in sides:
            raw=np.memmap(s['file'],dtype=np.uint8,mode='r')
            for tr in s['tracks']:
                meta=album['tracks'][tr['index']];a,b=int(tr['start']*FS),min(int(tr['end']*FS),s['frames']);u=np.asarray(raw[a*6:b*6]).reshape(-1,3).astype(np.int32)
                x=(u[:,0]|(u[:,1]<<8)|(u[:,2]<<16));x=np.where(x>=1<<23,x-(1<<24),x).reshape(-1,2).astype(np.float64)*gain;fade=min(480,len(x)//4);ramp=np.linspace(0,1,fade)[:,None];x[:fade]*=ramp;x[-fade:]*=ramp[::-1]
                pcm=np.clip(np.round(x),-2**23,2**23-1).astype('<i4').reshape(-1,1).view(np.uint8).reshape(-1,4)[:,:3].tobytes()
                name=(f"{meta['disc']}-" if album['discs']>1 else '')+f"{meta['position']:02d} - {safe(meta['title'])}.flac";out=folder/name
                subprocess.run(['flac','--silent','--force','--best','--force-raw-format','--endian=little','--sign=signed','--channels=2','--bps=24','--sample-rate=48000','-o',str(out),'-'],input=pcm,check=True)
                f=mutagen.flac.FLAC(out);f['title']=meta['title'];f['artist']=meta['artist'] or album['artist'];f['albumartist']=album['artist'];f['album']=album['title'];f['tracknumber']=str(meta['position'])
                f['discnumber']=str(meta['disc']);f['disctotal']=str(album['discs']);f['media']='Vinyl';f['musicbrainz_albumid']=mbid;f['comment']=f'Ripped from vinyl with the Vinyl ADC, {time.strftime("%Y-%m-%d")}; album gain {gain_db:+.1f} dB'
                if album['date']:f['date']=album['date']
                if meta['recording']:f['musicbrainz_trackid']=meta['recording']
                if cover:
                    pic=mutagen.flac.Picture();pic.type=3;pic.mime='image/jpeg';pic.data=cover;f.clear_pictures();f.add_picture(pic)
                f.save();files.append(name);self.log(f'Encoded {name}')
        manifest=[{'name':n,'size':(folder/n).stat().st_size,'sha256':hashlib.sha256((folder/n).read_bytes()).hexdigest()} for n in files+(['cover.jpg'] if cover else [])]
        with self.lock:album.update(status='ready',folder=str(folder.relative_to(self.home/'library')),files=manifest,gain_db=round(float(gain_db),1));self.save()
        self.log(f'“{album["title"]}” is ready for the media server: {len(files)} tracks, album gain {gain_db:+.1f} dB')
    def cover(self,mbid):
        path=self.home/'covers'/f'{mbid}.jpg';path.parent.mkdir(exist_ok=True)
        if path.exists():return path.read_bytes() or None
        try:data=http_get(f'https://coverartarchive.org/release/{mbid}/front-500','image/jpeg')
        except Exception:data=b''
        if not data:                                    # many pressings have no scan of their own: the release group's cover is the same artwork
            try:
                group=http_json(f'https://musicbrainz.org/ws/2/release/{mbid}?fmt=json&inc=release-groups')['release-group']['id']
                data=http_get(f'https://coverartarchive.org/release-group/{group}/front-500','image/jpeg')
            except Exception:data=b''
        path.write_bytes(data);return data or None        # an empty file remembers "no cover" so it is not asked for again and again
    def worker(self):
        while True:
            kind,arg=self.jobs.get()
            try:{'split':self.split_side,'finalize':self.finalize,'identify':self.identify,'purge':self.purge}[kind](arg)
            except Exception as e:self.log(f'{kind} failed: {e!r}')
            finally:self.jobs.task_done()
    # ---- what the dashboard sees
    def snapshot(self):
        with self.lock:
            s=self.side;album=self.store['albums'].get((s or {}).get('album') or self.store['current_album'] or '')
            if s:env=np.column_stack((np.array(s['peaks']),np.array(s['level']))) if s['peaks'] else np.zeros((0,3));gaps=s['gaps'];seconds=s['frames']/FS
            else:env=np.array(self.recent) if self.recent else np.zeros((0,3));gaps=[];seconds=0.
            step=max(1,len(env)//1200);n=len(env)//step*step;wave={'step_s':.1*step,'left':[],'right':[],'level':[]}
            if n:
                e=env[:n].reshape(-1,step,3);wave.update(left=[round(float(v),4) for v in e[:,:,0].max(axis=1)],right=[round(float(v),4) for v in e[:,:,1].max(axis=1)],level=[round(float(v),1) for v in e[:,:,2].max(axis=1)])
            now=None
            if album:
                now={'mbid':album['mbid'],'artist':album['artist'],'title':album['title'],'date':album['date'],'status':album['status'],'next_track':album['next_track'],'track_count':len(album['tracks']),
                     'tracklist':[{'index':i,'label':f"{(str(x['disc'])+'-') if album['discs']>1 else ''}{x['number'] or x['position']} · {x['title']}"} for i,x in enumerate(album['tracks'])]}
                if s:
                    start=s['first'] if s.get('first') is not None else album['next_track'];rest=album['tracks'][start:];t=max(0.,seconds-self.cfg['preroll_seconds']);acc=0.;idx=0
                    for i,tr in enumerate(rest):
                        idx=i
                        if tr['length'] is None or t<acc+tr['length']:break
                        acc+=tr['length']
                    now['ident']=s.get('ident')
                    if rest:now['track']={**rest[idx],'elapsed':round(t-acc,1),'number_in_album':start+idx+1};now['expected']=[round(float(v)+self.cfg['preroll_seconds'],1) for v in np.cumsum([x['length'] or 0 for x in rest])[:-1] if v]
            return {'seq':self.seq,'status':self.status,'message':self.message,'meters':self.meters,'recording':{'id':s['id'],'seconds':round(seconds,1),'quiet':round(sum(self.still)*.1,1)} if s else None,'wave':wave,'gaps':gaps,
                    'now':now,'config':self.cfg,'acoustid':bool(self.acoustid),'hold':max(0.,self.hold_until-time.time()),'events':list(self.events),'albums':[{k:a.get(k) for k in ('mbid','artist','title','date','status','next_track','gain_db','folder')}|{'track_count':len(a['tracks'])} for a in self.store['albums'].values()],
                    'sides':[{k:x.get(k) for k in ('id','started','seconds','status','album','tracks','recovered')} for x in self.store['sides'][-12:]],'current_album':self.store['current_album']}

# ------------------------------------------------------------------ HTTP
def make_handler(rip):
    page=(Path(__file__).with_name('ripper.html')).read_bytes
    class H(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def reply(self,body,ctype='application/json',code=200):
            if not isinstance(body,bytes):body=json.dumps(body).encode()
            self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            url=urllib.parse.urlparse(self.path);q=urllib.parse.parse_qs(url.query)
            try:
                if url.path=='/':self.reply(page(),'text/html; charset=utf-8')
                elif url.path=='/api/state':self.reply(rip.snapshot())
                elif url.path=='/api/search':
                    try:self.reply({'results':mb_search(q.get('q',[''])[0])})
                    except urllib.error.HTTPError as e:self.reply({'error':f'MusicBrainz is busy (HTTP {e.code}). Wait a few seconds and search again.'})
                    except Exception as e:self.reply({'error':f'Could not reach MusicBrainz: {e}'})
                elif url.path=='/outbox.json':
                    with rip.lock:self.reply([{'album':a['mbid'],'folder':a['folder'],'files':a['files']} for a in rip.store['albums'].values() if a.get('status')=='ready'])
                elif url.path.startswith('/outbox/'):
                    _,_,mbid,name=url.path.split('/',3);name=urllib.parse.unquote(name)
                    with rip.lock:a=rip.store['albums'][mbid];ok=any(f['name']==name for f in a['files'])
                    if not ok:return self.reply({'error':'not in the manifest'},code=404)
                    self.reply((rip.home/'library'/a['folder']/name).read_bytes(),'application/octet-stream')
                elif url.path=='/api/audio':               # the last N seconds of decimated audio, float32 interleaved stereo at 48 kHz
                    n=min(60,max(1,int(float(q.get('seconds',['10'])[0]))));blocks=list(rip.ring)[-n*2:]
                    data=(np.concatenate(blocks,axis=1).T.astype('<f4').tobytes() if blocks else b'')
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(data)));self.send_header('X-Rate',str(FS));self.send_header('X-Channels','2');self.end_headers();self.wfile.write(data)
                elif url.path.startswith('/cover/'):
                    mbid=url.path.split('/')[2]
                    if not re.fullmatch(r'[0-9a-f-]{36}',mbid):return self.reply({'error':'bad id'},code=400)
                    data=rip.cover(mbid)
                    if not data:return self.reply({'error':'no cover'},code=404)
                    self.send_response(200);self.send_header('Content-Type','image/jpeg');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','public, max-age=604800');self.end_headers();self.wfile.write(data)
                else:self.reply({'error':'not found'},code=404)
            except Exception as e:self.reply({'error':repr(e)},code=500)
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
            try:
                if self.path=='/api/select':
                    album=mb_release(body['mbid']);album.update(next_track=0,status='selected')
                    with rip.lock:
                        rip.store['albums'].setdefault(album['mbid'],album);rip.store['current_album']=album['mbid']
                        if rip.side:rip.side['album']=album['mbid']
                        rip.save()
                    rip.log(f'Album selected: {album["artist"]} — {album["title"]} ({len(album["tracks"])} tracks)');self.reply({'ok':True})
                elif self.path=='/api/next_track':          # "this side starts at track N": for the side being recorded and the next ones
                    with rip.lock:a=rip.store['albums'][body['mbid']];a['next_track']=max(0,min(len(a['tracks'])-1,int(body['index'])));rip.save()
                    self.reply({'ok':True})
                elif self.path=='/api/side/assign':         # attach a recorded side to an album from a given track, or detach it (mbid null); re-cuts it
                    with rip.lock:
                        side=next(s for s in rip.store['sides'] if s['id']==body['id']);old=rip.store['albums'].get(side['album'] or '')
                        side.update(album=body.get('mbid'),tracks=[],status='recorded')
                        if body.get('first') is not None:side['anchor']=None            # a chosen start track overrides what the fingerprint found
                        if old:rip.recount(old)
                        rip.save()
                    if body.get('mbid'):rip.jobs.put(('split',(side['id'],int(body['first'])) if body.get('first') is not None else side['id']))
                    self.reply({'ok':True})
                elif self.path=='/api/side/trash':          # nothing is deleted: the files move to ~/vinyl/trash
                    with rip.lock:side=next(s for s in rip.store['sides'] if s['id']==body['id'])
                    rip.trash_side(side);rip.log(f'Side {side["id"]} moved to the trash folder');self.reply({'ok':True})
                elif self.path=='/api/hold':                # measurements: do not start a side while test signals are on the input
                    rip.hold_until=time.time()+float(body.get('seconds',0));self.reply({'ok':True,'until':rip.hold_until})
                elif self.path=='/api/identify':
                    rip.jobs.put(('identify',(body['id'],'closed')));self.reply({'ok':True})
                elif self.path=='/api/clear':
                    with rip.lock:rip.store['current_album']=None;rip.save()
                    self.reply({'ok':True})
                elif self.path=='/api/record':rip.manual=body.get('action');self.reply({'ok':True})
                elif self.path=='/api/finalize':rip.jobs.put(('finalize',body['mbid']));self.reply({'ok':True})
                elif self.path=='/api/config':
                    with rip.lock:
                        for k,v in body.items():
                            if k in DEFAULTS:rip.cfg[k]=type(DEFAULTS[k])(v)
                        rip.save()
                    self.reply({'ok':True})
                elif self.path=='/outbox/ack':
                    with rip.lock:rip.store['albums'][body['album']].update(status='delivered',delivered=time.time());rip.save()
                    rip.log(f'Delivered to the media server: {rip.store["albums"][body["album"]]["title"]}');self.reply({'ok':True})
                else:self.reply({'error':'not found'},code=404)
            except Exception as e:self.reply({'error':repr(e)},code=400)
    return H

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port',type=int,default=8091);p.add_argument('--home',default='~/vinyl');p.add_argument('--replay');p.add_argument('--fast',action='store_true',help='with --replay: do not pace to real time')
    a=p.parse_args();rip=Ripper(a.home,a.replay,a.fast);threading.Thread(target=rip.worker,daemon=True).start()
    if a.replay and a.fast:rip.capture_loop();print(json.dumps({'sides':rip.store['sides'],'events':[e['text'] for e in rip.events]},indent=1)[:3000]);return
    loop=threading.Thread(target=rip.capture_loop);loop.start();print(f'Vinyl ripper dashboard on port {a.port}',flush=True)
    server=ThreadingHTTPServer(('0.0.0.0',a.port),make_handler(rip));threading.Thread(target=server.serve_forever,daemon=True).start()
    def shutdown(*_):rip.stop.set()
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    loop.join();server.shutdown()      # a restart or power-down closes the side being recorded instead of losing it
if __name__=='__main__':main()
