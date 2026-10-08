#!/usr/bin/env python3
"""The Discogs collection, for the ripper: which records are on the shelf, each mapped to a MusicBrainz release.

    ~/vinyl/discogs.token        a Discogs personal access token (discogs.com/settings/developers, "Generate new token"), one line
    config 'discogs_user'        the Discogs username; empty (the default) means "ask Discogs whose token this is" (/oauth/identity)

Without the token nothing here runs and the dashboard says "not configured". Everything is cached in ~/vinyl/discogs.json and the
covers in ~/vinyl/covers/discogs/{id}.jpg, fetched once. A sync is a chain of short steps on the ripper's job queue, each stopping
after about 20 s and saving where it got to: a side that closes meanwhile is cut and identified without waiting for the whole
collection, and a restart carries on where the last run stopped. Nothing is ever written to Discogs.

Discogs knows nothing about MusicBrainz, so every record is looked up there: first the Discogs link MusicBrainz keeps on its own
releases (exact), then the barcode, then artist and title preferring a vinyl pressing with the same number of tracks. A record
nothing convincing comes back for stays Discogs-only and is asked about again after a month (MusicBrainz grows).
"""
import json,re,threading,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path

API='https://api.discogs.com';MB='https://musicbrainz.org/ws/2';DAY=86400.
SIZES=('LP','EP','7"','10"','12"','Single','Maxi-Single','Mini-Album')

def artists(lst):
    """Discogs credits as one line, without the '(2)' it adds to tell namesakes apart: Simon (3) & Garfunkel -> 'Simon & Garfunkel'."""
    out=''
    for a in lst or []:
        j=(a.get('join') or '').strip();out+=re.sub(r'\s+\(\d+\)$','',a.get('name') or '')+(', ' if j==',' else f' {j} ' if j else '')
    return out.strip(' ,')
def fmt(formats):
    """The medium and its size as a shelf label: 'Vinyl LP', '2×Vinyl LP', 'Vinyl 7"', 'CD'."""
    out=[]
    for f in formats or []:
        q=str(f.get('qty') or '1');n=int(q) if q.isdigit() else 1;size=[x for x in f.get('descriptions') or [] if x in SIZES][:1]
        out.append((f'{n}×' if n>1 else '')+' '.join([f.get('name') or '?']+size))
    return ', '.join(out)
def seconds(d):
    """'3:45' or '1:02:03' -> seconds; Discogs leaves many durations empty."""
    parts=(d or '').strip().split(':')
    if not all(p.isdigit() for p in parts):return None
    s=0
    for p in parts:s=s*60+int(p)
    return s or None
def side_of(pos):
    """The side a track position is on: 'A1' -> 'A', 'B' -> 'B', 'AA2' -> 'AA', '2-5' (CD 2, track 5) -> '2', '7' -> None."""
    m=re.match(r'\s*([A-Za-z]+)',pos or '') or re.match(r'\s*(\d+)[-.]\d',pos or '')
    return m[1].upper() if m else None
def basic(item):
    """One entry of a collection page, as kept: what the shelf view needs."""
    b=item.get('basic_information') or {};cover=b.get('cover_image') or ''
    return {'id':b.get('id') or item.get('id'),'artist':artists(b.get('artists')),'title':b.get('title',''),'year':b.get('year') or None,'format':fmt(b.get('formats')),
            'vinyl':any(f.get('name')=='Vinyl' for f in b.get('formats') or []),'labels':[{'name':re.sub(r'\s+\(\d+\)$','',l.get('name','')),'catno':l.get('catno','')} for l in b.get('labels') or []],
            'cover_url':'' if 'spacer.gif' in cover else cover,'master':b.get('master_id') or None,'added':item.get('date_added','')}    # spacer.gif: Discogs has no image
def detail(r):
    """A /releases/{id} answer, as kept: the tracklist with its side positions (headings dropped, index tracks opened), barcodes, country."""
    rows=[x for t in r.get('tracklist') or [] for x in ((t.get('sub_tracks') or []) if t.get('type_')=='index' else [t] if t.get('type_','track')=='track' else [])]
    imgs=r.get('images') or []
    return {'tracklist':[{'position':x.get('position',''),'side':side_of(x.get('position')),'title':x.get('title',''),'duration':seconds(x.get('duration')),'artist':artists(x.get('artists'))} for x in rows],
            'barcodes':sorted({c for c in (re.sub(r'\D','',i.get('value') or '') for i in r.get('identifiers') or [] if i.get('type')=='Barcode') if len(c)>=8}),
            'country':r.get('country',''),'released':r.get('released',''),'url':r.get('uri',''),
            'formats':[{'name':f.get('name'),'qty':f.get('qty'),'descriptions':f.get('descriptions') or [],'text':f.get('text','')} for f in r.get('formats') or []],
            'image':next((i.get('uri') for i in imgs if i.get('type')=='primary'),None) or next((i.get('uri') for i in imgs),None)}
def sides(tracklist):
    """[{'side':'A','tracks':['A1','A2']},...] in the order the record plays."""
    out=[]
    for t in tracklist:
        if not out or out[-1]['side']!=t['side']:out.append({'side':t['side'],'tracks':[]})
        out[-1]['tracks'].append(t['position'])
    return out
def clean(s):return re.sub(r'["\\]',' ',s or '').strip()                # a Lucene phrase cannot hold quotes or backslashes
def pick(hits,n,year):
    """The most convincing MusicBrainz release among search hits, and how convincing (0-1): the search score, a vinyl medium, the same track count, the same year."""
    def rate(x):
        vinyl=any('vinyl' in (m.get('format') or '').lower() for m in x.get('media') or []);tc=x.get('track-count') or sum(m.get('track-count') or 0 for m in x.get('media') or [])
        return .4*x.get('score',0)/100+.3*vinyl+(.2*(tc==n) if n else .1)+.1*(bool(year) and (x.get('date') or '')[:4]==str(year))
    best=max(hits,key=lambda x:(rate(x),x.get('score',0)));return best,round(rate(best),2)

class Client:
    """Discogs over HTTP: 60 authenticated requests a minute, and every answer says how many are left (X-Discogs-Ratelimit-Remaining).
    Requests are spaced a second apart, a nearly spent window is waited out, and a 429 is retried after the Retry-After it names."""
    def __init__(self,token,ua,sleep=time.sleep,urlopen=urllib.request.urlopen):
        self.token,self.ua,self.sleep,self.urlopen=token,ua,sleep,urlopen;self.last=0.;self.remaining=None;self.lock=threading.Lock()
    def get(self,url,accept='application/json'):
        if url.startswith('/'):url=API+url
        with self.lock:
            for attempt in range(5):
                wait=1.-(time.time()-self.last)
                if self.remaining is not None and self.remaining<=2:wait=max(wait,30.)     # a moving one-minute window: half a minute frees most of it
                if wait>0:self.sleep(wait)
                self.last=time.time()
                try:
                    with self.urlopen(urllib.request.Request(url,headers={'User-Agent':self.ua,'Authorization':f'Discogs token={self.token}','Accept':accept}),timeout=25) as r:
                        rem=str(r.headers.get('X-Discogs-Ratelimit-Remaining') or '');self.remaining=int(rem) if rem.isdigit() else None;return r.read()
                except urllib.error.HTTPError as e:
                    if e.code not in (429,500,502,503) or attempt==4:raise
                    ra=str((e.headers or {}).get('Retry-After') or '');self.remaining=None;self.sleep(float(ra) if ra.isdigit() else 15.*(attempt+1))

class Collection:
    def __init__(self,home,ua,mb_json,log=print,user=lambda:'',client=None,clock=time.time):
        self.home=Path(home);self.path=self.home/'discogs.json';self.covers=self.home/'covers'/'discogs';self.mb=mb_json;self.log=log;self.user=user;self.clock=clock
        tok=self.home/'discogs.token';token=tok.read_text().strip() if tok.exists() else ''
        self.client=client or (Client(token,ua) if token else None);self.lock=threading.RLock();self.queued=False
        self.data={'user':None,'synced':0,'finished':0,'releases':{},'order':[],'sync':None,'error':None,'error_at':0,'rev':0}
        if self.path.exists():
            try:self.data.update(json.loads(self.path.read_text()))
            except ValueError:self.log('discogs.json is unreadable; the collection is read again from Discogs')
    def configured(self):return self.client is not None
    def save(self):
        with self.lock:self.data['rev']+=1;tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data));tmp.replace(self.path)
    def done(self,r):
        mb=r.get('mb')
        return 'detail' in r and 'cover' in r and mb is not None and (mb.get('mbid') is not None or self.clock()-mb.get('checked',0)<30*DAY)
    def pending(self):
        with self.lock:return [k for k in self.data['order'] if k in self.data['releases'] and not self.done(self.data['releases'][k])]
    def stale(self):
        """The list itself is read again once a day, and at 04:00 so the night's purchases are in by morning."""
        age=self.clock()-self.data['synced'];return age>DAY or (time.localtime(self.clock()).tm_hour==4 and age>6*3600)
    def due(self):
        """Should a sync start now: overdue, interrupted by a restart, or records left half-done. Not within 15 min of a failure."""
        if not self.configured() or self.queued or self.clock()-self.data.get('error_at',0)<900:return False
        return bool(self.data.get('sync')) or self.stale() or bool(self.pending())
    def start(self,full=None):
        """Begin or resume a sync (the caller queues step()). full: read the collection list again, not only finish the records in it."""
        with self.lock:
            d=self.data;now=self.clock();full=self.stale() if full is None else full
            if full and (d.get('sync') or {}).get('phase')!='pages':d['sync']={'phase':'pages','page':1,'seen':[],'started':now}
            elif not d.get('sync'):d['sync']={'phase':'items','started':now}
            d['error']=None;d['error_at']=0;self.save()
    def step(self,budget=20.,stop=lambda:False):
        """About `budget` seconds of sync; True when there is more to do. A network failure stops the sync where it is (it resumes later)."""
        t0=time.monotonic()
        try:
            while time.monotonic()-t0<budget:
                if stop():return True
                with self.lock:s=self.data.get('sync')
                if not s:return False
                if s['phase']=='pages':self.page(s);continue
                todo=self.pending()
                if not todo:
                    with self.lock:self.data.update(sync=None,finished=self.clock());self.save();st=self.status()
                    self.log(f'Discogs: {st["owned"]} records, {st["matched"]} matched to MusicBrainz, {st["unmatched"]} not');return False
                self.item(todo[0])
            return True
        except Exception as e:
            with self.lock:self.data.update(error=repr(e),error_at=self.clock());self.save()
            self.log(f'Discogs sync paused: {e!r}; it carries on later');return False
    def whoami(self):
        u=(self.user() or '').strip() or self.data.get('user')
        return u or json.loads(self.client.get('/oauth/identity'))['username']
    def page(self,s):
        user=self.whoami();q=urllib.parse.urlencode({'per_page':100,'page':s['page'],'sort':'added','sort_order':'desc'})
        r=json.loads(self.client.get(f'/users/{urllib.parse.quote(user)}/collection/folders/0/releases?{q}'))
        with self.lock:
            rel=self.data['releases'];self.data['user']=user
            for it in r.get('releases') or []:
                b=basic(it);k=str(b['id'])
                if k in s['seen']:continue                          # a second copy of the same pressing
                rel[k]={**rel.get(k,{}),**b};s['seen'].append(k)
            if s['page']>=(r.get('pagination') or {}).get('pages',1):
                seen=set(s['seen'])
                for k in [k for k in rel if k not in seen]:del rel[k]    # sold or given away
                self.data.update(order=s['seen'],synced=self.clock(),sync={'phase':'items','started':s['started']})
                self.log(f'Discogs: {len(seen)} records in {user}’s collection')
            else:s['page']+=1
            self.save()
    def put(self,k,**kw):
        with self.lock:
            if k in self.data['releases']:self.data['releases'][k].update(kw)
    def item(self,k):
        """Fill in one record: its tracklist and barcodes, its cover, its MusicBrainz release. Each part is kept as soon as it is known."""
        with self.lock:r=dict(self.data['releases'][k])
        if 'detail' not in r:
            try:r['detail']=detail(json.loads(self.client.get(f'/releases/{k}')))
            except urllib.error.HTTPError as e:
                if e.code!=404:raise
                r['detail']=None                                    # gone from Discogs: map it by artist and title alone
            self.put(k,detail=r['detail'])
        if 'cover' not in r:r['cover']=self.fetch_cover(k,r.get('cover_url') or (r['detail'] or {}).get('image'));self.put(k,cover=r['cover'])
        if r.get('mb') is None or not self.done(r):self.put(k,mb=self.map_mb(r))
        self.save()
    def fetch_cover(self,k,url):
        if not url:return False
        try:data=self.client.get(url,'image/*')
        except urllib.error.HTTPError as e:
            if e.code in (403,404):return False
            raise
        self.covers.mkdir(parents=True,exist_ok=True);(self.covers/f'{k}.jpg').write_bytes(data);return bool(data)
    def search(self,q):return self.mb(f'{MB}/release/?fmt=json&limit=25&query='+urllib.parse.quote(q)).get('releases',[])
    def map_mb(self,r):
        """(a) the Discogs link on a MusicBrainz release, (b) the barcode, (c) artist and title; {'mbid':None} when nothing convinces."""
        det=r.get('detail') or {};n=len(det.get('tracklist') or []) or None;now=self.clock();res=lambda mbid,how,conf,group:{'mbid':mbid,'how':how,'confidence':conf,'group':group,'checked':now}
        try:j=self.mb(f'{MB}/url?resource={urllib.parse.quote("https://www.discogs.com/release/"+str(r["id"]),safe="")}&inc=release-rels&fmt=json')
        except urllib.error.HTTPError as e:
            if e.code not in (400,404):raise
            j={}                                                    # 404: no MusicBrainz release links to this pressing
        ids=list(dict.fromkeys(x['release']['id'] for x in j.get('relations') or [] if x.get('target-type')=='release' and x.get('release')))
        if ids:
            try:group=self.mb(f'{MB}/release/{ids[0]}?fmt=json&inc=release-groups')['release-group']['id']
            except Exception:group=None
            return res(ids[0],'url',1. if len(ids)==1 else .9,group)
        for code in det.get('barcodes') or []:
            hits=[x for x in self.search(f'barcode:{code}') if re.sub(r'\D','',x.get('barcode') or '')==code]
            if hits:best,conf=pick(hits,n,r.get('year'));return res(best['id'],'barcode',round(.7+.3*conf,2),(best.get('release-group') or {}).get('id'))
        if r.get('title') and r.get('artist'):
            hits=[x for x in self.search(f'release:"{clean(r["title"])}" AND artist:"{clean(r["artist"])}"') if x.get('score',0)>=90]
            if hits:
                best,conf=pick(hits,n,r.get('year'))
                if conf>=.6:return res(best['id'],'search',conf,(best.get('release-group') or {}).get('id'))
        return res(None,None,0.,None)
    # ---- what the ripper asks
    def owned(self):
        """The MusicBrainz releases on the shelf, and their release groups (other pressings of the same album)."""
        with self.lock:m=[r['mb'] for r in self.data['releases'].values() if (r.get('mb') or {}).get('mbid')]
        return {x['mbid'] for x in m},{x['group'] for x in m if x.get('group')}
    def owned_in_group(self,group):
        if not group:return None
        with self.lock:return next((r['mb']['mbid'] for k in self.data['order'] for r in [self.data['releases'].get(k) or {}] if (r.get('mb') or {}).get('mbid') and r['mb'].get('group')==group),None)
    def status(self):
        if not self.configured():return {'configured':False}
        with self.lock:
            d=self.data;rel=list(d['releases'].values());s=d.get('sync')
            return {'configured':True,'user':d.get('user'),'owned':len(rel),'matched':sum(1 for r in rel if (r.get('mb') or {}).get('mbid')),'unmatched':sum(1 for r in rel if r.get('mb') and not r['mb'].get('mbid')),
                    'pending':len(self.pending()),'synced':d['synced'] or None,'finished':d.get('finished') or None,'running':bool(s) and not d.get('error'),'phase':(s or {}).get('phase'),
                    'error':d.get('error'),'rev':d['rev']}
    def compact(self,k,r):
        mb=r.get('mb') or {}
        return {'id':int(k),'artist':r.get('artist',''),'title':r.get('title',''),'year':r.get('year'),'format':r.get('format',''),'vinyl':r.get('vinyl',False),
                'label':', '.join(dict.fromkeys(' '.join(x for x in (l['name'],l['catno']) if x) for l in r.get('labels') or [])),'cover':f'/covers/discogs/{k}.jpg' if r.get('cover') else None,
                'mbid':mb.get('mbid'),'match':mb.get('how'),'confidence':mb.get('confidence'),'added':r.get('added','')}
    def records(self,q=''):
        words=re.findall(r'\w+',(q or '').lower())
        with self.lock:out=[self.compact(k,self.data['releases'][k]) for k in self.data['order'] if k in self.data['releases']]
        return [r for r in out if all(w in f"{r['artist']} {r['title']} {r['year'] or ''} {r['label']}".lower() for w in words)]
    def record(self,k):
        with self.lock:
            r=self.data['releases'].get(str(k))
            if r is None:return None
            det=r.get('detail') or {};out=self.compact(str(k),r)
        tl=det.get('tracklist') or []
        return {**out,'labels':r.get('labels') or [],'master':r.get('master'),'group':(r.get('mb') or {}).get('group'),'country':det.get('country',''),'released':det.get('released',''),
                'barcodes':det.get('barcodes') or [],'formats':det.get('formats') or [],'discogs_url':det.get('url') or f'https://www.discogs.com/release/{k}',
                'tracklist':tl,'sides':sides(tl),'detail':'detail' in r}
