#!/usr/bin/env python3
"""Offline tests of the Discogs collection: paging and rate limits, MusicBrainz mapping, resuming, the shelf API and ranking.
No network: Discogs answers come from fixtures shaped like the documented API, MusicBrainz from a fake.

    python3 pi/test_discogs.py
"""
import io,json,queue,sys,tempfile,threading,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));import ripper as R,discogs as D

# ---- fixtures, in the shapes of the Discogs API documentation
def item(i,artist,title,year=1999,fmt=('Vinyl','1',['LP','Album']),cover=True):
    """One entry of /users/{u}/collection/folders/0/releases."""
    return {'id':i,'instance_id':i*10,'date_added':f'2026-0{1+i%9}-01T10:00:00-07:00','rating':0,
            'basic_information':{'id':i,'master_id':i+1000,'title':title,'year':year,'cover_image':f'https://i.discogs.com/{i}.jpg' if cover else 'https://s.discogs.com/images/spacer.gif',
                                 'formats':[{'name':fmt[0],'qty':fmt[1],'descriptions':fmt[2]}],'labels':[{'name':'Parlophone (2)','catno':f'CAT{i}'}],
                                 'artists':[{'name':a,'anv':'','join':j,'role':''} for a,j in (artist if isinstance(artist,list) else [(artist,'')])]}}
def page(n,pages,items):return {'pagination':{'page':n,'pages':pages,'per_page':100,'items':0,'urls':{}},'releases':items}
def release_detail(i,tracks,barcode=None):
    """/releases/{id}: a heading, sides A and B, an index track with sub-tracks."""
    tl=[{'type_':'heading','position':'','title':'Side One','duration':''}]+[{'type_':'track','position':p,'title':f'Song {p}','duration':'3:30'} for p in tracks]
    return {'id':i,'title':'x','uri':f'https://www.discogs.com/release/{i}-x','country':'UK','released':'1999-05-01','tracklist':tl,
            'identifiers':[{'type':'Barcode','value':barcode}] if barcode else [{'type':'Matrix / Runout','value':'XYZ 1'}],'images':[{'type':'primary','uri':f'https://i.discogs.com/{i}-big.jpg'}],
            'formats':[{'name':'Vinyl','qty':'1','descriptions':['LP']}]}
COLLECTION=[page(1,2,[item(1,'Radiohead','Kid A',2000),item(2,'Portishead','Dummy',1994),item(2,'Portishead','Dummy',1994)]),   # a second copy of Dummy
            page(2,2,[item(3,[('Simon (3)','&'),('Nobody','')],'Obscure',1971,cover=False),item(4,'Air','Moon Safari',1998,('Vinyl','2',['LP']))])]
DETAILS={1:release_detail(1,['A1','A2','B1','B2']),2:release_detail(2,['A1','A2','B1'],'5 012345 678900'),3:{**release_detail(3,['A','B']),'images':[]},4:release_detail(4,['A1','B1','C1','D1'])}

class FakeDiscogs:
    """Stands in for discogs.Client: answers by URL and remembers who asked (which thread)."""
    def __init__(self,pages=COLLECTION,details=DETAILS):self.pages,self.details,self.calls,self.threads=pages,details,[],set()
    def get(self,url,accept='application/json'):
        self.calls.append(url);self.threads.add(threading.current_thread().name)
        if url=='/oauth/identity':return json.dumps({'id':1,'username':'mads'}).encode()
        if '/collection/folders/0/releases' in url:return json.dumps(self.pages[int(urllib.parse.parse_qs(url.split('?')[1])['page'][0])-1]).encode()
        if url.startswith('/releases/'):return json.dumps(self.details[int(url.rsplit('/',1)[1])]).encode()
        if url.startswith('https://i.discogs.com/'):return b'\xff\xd8JPEG'
        raise AssertionError(url)
def mb_hit(mbid,fmt='12" Vinyl',tracks=4,score=100,barcode='',group='rg-'):
    return {'id':mbid,'score':score,'date':'2000','barcode':barcode,'track-count':tracks,'media':[{'format':fmt,'track-count':tracks}],'release-group':{'id':group+mbid}}
class FakeMB:
    """MusicBrainz: Kid A is linked from its Discogs page, Dummy is found by barcode, Moon Safari by search (vinyl beats CD), Obscure not at all."""
    def __init__(self):self.calls=[]
    def __call__(self,url):
        self.calls.append(url)
        if '/url?' in url:
            if 'release%2F1&' in url:return {'relations':[{'type':'discogs','target-type':'release','release':{'id':'mb-kid-a'}}]}
            raise urllib.error.HTTPError(url,404,'Not Found',{},None)
        if '/release/mb-kid-a?' in url:return {'release-group':{'id':'rg-kid-a'}}
        if 'barcode%3A5012345678900' in url:return {'releases':[mb_hit('mb-dummy-cd','CD',3,barcode='5012345678900'),mb_hit('mb-dummy',tracks=3,barcode='5012345678900'),mb_hit('mb-other',barcode='999')]}
        if 'Moon%20Safari' in url:return {'releases':[mb_hit('mb-moon-cd','CD',4),mb_hit('mb-moon',tracks=4),mb_hit('mb-moon-bad',score=60)]}
        return {'releases':[]}

def collection(tmp,**kw):
    return D.Collection(tmp,'test',kw.pop('mb',None) or FakeMB(),log=lambda t:None,client=kw.pop('client',None) or FakeDiscogs(),**kw)

# ---- the client: spacing, the remaining-requests header and 429
class Resp(io.BytesIO):
    def __init__(self,body,remaining):super().__init__(body);self.headers={'X-Discogs-Ratelimit-Remaining':str(remaining)}
    def __enter__(self):return self
    def __exit__(self,*a):pass
def test_client_rate_limit():
    slept=[];answers=[Resp(b'1',59),Resp(b'2',2),urllib.error.HTTPError('u',429,'Too Many',{'Retry-After':'7'},None),Resp(b'3',58)];seen=[]
    def urlopen(req,timeout):
        seen.append(req);a=answers.pop(0)
        if isinstance(a,Exception):raise a
        return a
    c=D.Client('TOKEN','VinylADC-test/1',sleep=slept.append,urlopen=urlopen)
    assert c.get('/a')==b'1' and seen[0].get_header('Authorization')=='Discogs token=TOKEN' and seen[0].get_header('User-agent')=='VinylADC-test/1' and seen[0].full_url=='https://api.discogs.com/a'
    assert c.get('/b')==b'2' and slept and .5<slept[-1]<=1.,'requests are spaced a second apart'
    slept.clear();assert c.get('/c')==b'3',slept
    assert slept[0]>=30,'two left in the window: wait it out';assert 7. in slept,'a 429 waits for its Retry-After and retries'

# ---- sync: pages, duplicates, details, covers, mapping, resuming
def test_sync_pages_and_mapping():
    with tempfile.TemporaryDirectory() as tmp:
        c=collection(tmp);c.start(True)
        assert c.step(budget=60,stop=lambda:len(c.client.calls)>=2) is True                  # identity and page 1, then "shutting down"
        assert c.data['sync']=={'phase':'pages','page':2,'seen':['1','2'],'started':c.data['sync']['started']},c.data['sync']
        # a restart: a new process reads discogs.json and carries on at page 2
        c2=collection(tmp);assert c2.due();c2.start()
        assert c2.data['sync']['page']==2 and c2.step(budget=60) is False
        assert c2.client.calls[0].startswith('/users/mads/collection/folders/0/releases?per_page=100&page=2'),'page 1 is not read again, nor the identity'
        assert c2.data['order']==['1','2','3','4'] and c2.data['synced'] and c2.data['sync'] is None
        r=c2.data['releases']
        assert r['3']['artist']=='Simon & Nobody' and r['3']['cover_url']=='' and r['3']['cover'] is False and r['4']['format']=='2×Vinyl LP' and r['1']['format']=='Vinyl LP'
        assert r['2']['detail']['barcodes']==['5012345678900'] and [t['position'] for t in r['1']['detail']['tracklist']]==['A1','A2','B1','B2']
        assert D.sides(r['1']['detail']['tracklist'])==[{'side':'A','tracks':['A1','A2']},{'side':'B','tracks':['B1','B2']}]
        assert (Path(tmp)/'covers'/'discogs'/'1.jpg').read_bytes()==b'\xff\xd8JPEG'
        # mapping order: the Discogs link, then the barcode, then the search; nothing for the obscure one
        assert (r['1']['mb']['mbid'],r['1']['mb']['how'],r['1']['mb']['group'])==('mb-kid-a','url','rg-kid-a'),r['1']['mb']
        assert (r['2']['mb']['mbid'],r['2']['mb']['how'])==('mb-dummy','barcode'),'the vinyl pressing with the barcode, not the CD'
        assert (r['4']['mb']['mbid'],r['4']['mb']['how'])==('mb-moon','search'),r['4']['mb']
        assert r['3']['mb']['mbid'] is None and r['3']['mb']['how'] is None
        mb=c2.mb.calls;assert not any('Kid%20A' in u for u in mb),'a Discogs link ends the search'
        assert not any('Dummy' in u for u in mb),'a barcode hit ends the search'
        st=c2.status();assert (st['owned'],st['matched'],st['unmatched'],st['pending'],st['running'])==(4,3,1,0,False),st
        # incremental: the next run reads the list again but fetches no detail, cover or MusicBrainz answer it already has
        c2.client.calls.clear();c2.mb.calls.clear();c2.start(True);c2.step(budget=60)
        assert all('/collection/' in u for u in c2.client.calls) and c2.mb.calls==[],(c2.client.calls,c2.mb.calls)
        assert not c2.due(),'nothing to do for a day'
        # a record sold: it leaves the shelf
        c2.client.pages=[page(1,1,[item(1,'Radiohead','Kid A',2000)])];c2.start(True);c2.step(budget=60);assert list(c2.data['releases'])==['1']

def test_sync_failure_pauses():
    with tempfile.TemporaryDirectory() as tmp:
        class Down(FakeDiscogs):
            def get(self,url,accept='application/json'):raise urllib.error.URLError('no route')
        c=collection(tmp,client=Down());c.start(True);assert c.step(budget=5) is False and 'no route' in c.data['error']
        assert not c.due(),'not again within 15 minutes';c.data['error_at']-=1000;assert c.due() and c.data['sync']['phase']=='pages'

# ---- ranking: the shelf beats a vinyl pressing; the album in use still comes first
def rel(mbid,fmt):return {'id':mbid,'title':'Kid A','mediums':[{'position':1,'format':fmt,'track_count':10,'tracks':[{'position':2}]}]}
def results():
    return [{'score':.93,'id':'a','recordings':[{'id':'rec','title':'Kid A','releasegroups':[
        {'id':'rg-kid-a','title':'Kid A','releases':[rel('mb-cd','CD'),rel('mb-vinyl','12" Vinyl'),rel('mb-mine','CD')]},
        {'id':'rg-best-of','title':'Best Of','releases':[{'id':'mb-best','mediums':[{'position':1,'format':'12" Vinyl','track_count':10,'tracks':[{'position':1}]}]}]}]}]}]
def test_rank_prefers_owned():
    assert R.rank_releases(results())[0]['release'] in ('mb-vinyl','mb-best'),'without a shelf: vinyl first, as before'
    m=R.rank_releases(results(),owned={'mb-mine'},groups={'rg-kid-a'});assert m[0]['release']=='mb-mine' and m[0]['owned'] and m[0]['match']==.93,m[0]
    m=R.rank_releases(results(),owned=set(),groups={'rg-kid-a'});assert m[0]['release']=='mb-vinyl' and m[1]['release'] in ('mb-cd','mb-mine') and m[1]['group']=='rg-kid-a','another pressing of an owned album beats an unowned vinyl'
    assert R.rank_releases(results(),current='mb-cd',owned={'mb-mine'})[0]['release']=='mb-cd','the album in use comes first'
    assert next(m for m in R.rank_releases(results()) if m['release']=='mb-best')['album']=='Best Of','a release without a title takes its group’s'

# ---- the ripper: API, CORS, select, not configured, not in the collection, threads
def album(mbid,group=None):
    return {'mbid':mbid,'title':'Kid A','artist':'Radiohead','date':'2000','discs':1,'group':group,
            'tracks':[{'disc':1,'position':i+1,'number':f'A{i+1}','title':f'T{i+1}','length':200.,'recording':f'r{i}','artist':'Radiohead'} for i in range(4)]}
def ripper(tmp,synced=True):
    rip=R.Ripper(tmp);rip.jobs=queue.Queue();rip.discogs=collection(tmp);rip.discogs.log=rip.log
    if synced:rip.discogs.start(True);rip.discogs.step(budget=60)
    return rip
def serve(rip):
    srv=R.ThreadingHTTPServer(('127.0.0.1',0),R.make_handler(rip));threading.Thread(target=srv.serve_forever,daemon=True).start();return srv,f'http://127.0.0.1:{srv.server_address[1]}'
def call(url,body=None):
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as r:return r.status,dict(r.headers),r.read()
    except urllib.error.HTTPError as e:return e.code,dict(e.headers),e.read()

def test_collection_api():
    with tempfile.TemporaryDirectory() as tmp:
        rip=ripper(tmp);R.mb_release=lambda mbid:album(mbid,'rg-kid-a');asked=[];orig=R.mb_release
        rip.store['albums']['mb-dummy']={**album('mb-dummy'),'status':'delivered','next_track':4};rip.store['sides'].append({'id':'s1','album':'mb-dummy','started':0,'seconds':1,'status':'split','tracks':[]})
        srv,base=serve(rip)
        try:
            code,h,body=call(base+'/api/collection');out=json.loads(body)
            assert code==200 and h['Access-Control-Allow-Origin']=='*' and out['configured'] and (out['owned'],out['matched'],out['unmatched'])==(4,3,1),out
            kid=out['records'][0];assert set(kid)>={'id','artist','title','year','format','cover','cover_url','mbid','match','ripped','rip_status','sides_recorded','added'},kid
            assert kid['id']==1 and kid['cover']=='/covers/discogs/1.jpg' and kid['cover_url']==base+'/covers/discogs/1.jpg' and kid['mbid']=='mb-kid-a' and kid['ripped'] is False
            dummy=out['records'][1];assert dummy['ripped'] and dummy['rip_status']=='delivered' and dummy['sides_recorded']==1 and out['records'][2]['cover'] is None
            assert [r['id'] for r in json.loads(call(base+'/api/collection?q=moon%20air')[2])['records']]==[4],'search box'
            code,h,body=call(base+'/api/collection/1');d=json.loads(body)
            assert code==200 and h['Access-Control-Allow-Origin']=='*' and d['sides'][1]=={'side':'B','tracks':['B1','B2']} and d['tracklist'][0]=={'position':'A1','side':'A','title':'Song A1','duration':210,'artist':''} and d['album'] is None,d
            assert call(base+'/api/collection/99')[0]==404
            code,h,body=call(base+'/covers/discogs/1.jpg');assert code==200 and body==b'\xff\xd8JPEG' and h['Content-Type']=='image/jpeg' and h['Access-Control-Allow-Origin']=='*'
            assert call(base+'/covers/discogs/3.jpg')[0]==404
            # rip this record: an unmatched one is refused with a reason, a matched one becomes the album for the next side
            code,h,body=call(base+'/api/collection/3/select',{});e=json.loads(body)
            assert code==409 and e['unmatched'] and 'MusicBrainz' in e['error'] and rip.store['current_album'] is None,e
            code,h,body=call(base+'/api/collection/1/select',{});assert code==200 and json.loads(body)['mbid']=='mb-kid-a'
            assert rip.store['current_album']=='mb-kid-a' and rip.store['albums']['mb-kid-a']['discogs']==1 and rip.store['albums']['mb-kid-a']['status']=='selected'
            R.mb_release=lambda mbid:asked.append(mbid) or orig(mbid);call(base+'/api/collection/1/select',{});assert asked==[],'a known album is not fetched again'
            assert json.loads(call(base+'/api/collection/1')[2])['album']['track_count']==4
            # in the shelf or not: the selected album is, a stranger is not
            st=json.loads(call(base+'/api/state')[2]);assert st['now']['not_in_collection'] is False and st['discogs']['owned']==4,st['now']
            rip.store['albums']['mb-x']={**album('mb-x','rg-x'),'status':'selected','next_track':0};rip.store['current_album']='mb-x'
            st=json.loads(call(base+'/api/state')[2]);assert st['now']['not_in_collection'] is True and {a['mbid']:a['not_in_collection'] for a in st['albums']}=={'mb-dummy':False,'mb-kid-a':False,'mb-x':True}
            rip.store['albums']['mb-y']={**album('mb-y','rg-kid-a'),'status':'selected','next_track':0};rip.store['current_album']='mb-y'
            assert json.loads(call(base+'/api/state')[2])['now']['not_in_collection'] is False,'another pressing of an owned album counts as owned'
            code,h,_=call(base+'/api/discogs/sync',{});assert code==200 and ('discogs',None) in list(rip.jobs.queue)
            req=urllib.request.Request(base+'/api/collection/1/select',method='OPTIONS')
            with urllib.request.urlopen(req,timeout=5) as r:assert r.status==204 and r.headers['Access-Control-Allow-Origin']=='*'
        finally:srv.shutdown();R.mb_release=orig

def test_not_configured():
    with tempfile.TemporaryDirectory() as tmp:
        rip=R.Ripper(tmp);rip.jobs=queue.Queue();srv,base=serve(rip)
        try:
            assert not rip.discogs.configured() and not rip.discogs.due()
            out=json.loads(call(base+'/api/collection')[2]);assert out=={'configured':False,'records':[]},out
            st=json.loads(call(base+'/api/state')[2]);assert st['discogs']=={'configured':False}
            code,_,body=call(base+'/api/discogs/sync',{});assert code==400 and 'discogs.token' in json.loads(body)['error'] and rip.jobs.empty()
            assert call(base+'/api/collection/1/select',{})[0]==404
            rip.discogs_tick();assert rip.jobs.empty()
        finally:srv.shutdown()

def test_sync_runs_on_the_worker_not_the_capture_thread():
    with tempfile.TemporaryDirectory() as tmp:
        rip=ripper(tmp,synced=False);fake=rip.discogs.client
        rip.housekeeping();rip.discogs_tick()                                  # what the capture and clock threads do: only a job is queued
        assert fake.calls==[] and list(rip.jobs.queue)==[('discogs',None)],(fake.calls,list(rip.jobs.queue))
        rip.discogs_tick();assert list(rip.jobs.queue)==[('discogs',None)],'never queued twice'
        rip.jobs.put(('purge',None))
        w=threading.Thread(target=rip.worker,name='worker',daemon=True);w.start();t0=time.time()
        while (rip.discogs.data['sync'] or not rip.discogs.data['synced']) and time.time()-t0<20:time.sleep(.05)
        rip.jobs.join();assert fake.threads=={'worker'} and rip.discogs.status()['matched']==3 and not rip.discogs.queued,fake.threads
        # long syncs go in short steps, so a side that closes meanwhile is not kept waiting behind the whole collection
        steps=[];real=rip.discogs.step;rip.discogs.step=lambda **kw:steps.append(1) or len(steps)<3
        rip.discogs_sync(True);rip.jobs.join();assert len(steps)==3
        rip.stop.set();steps.clear();rip.discogs_sync(True);rip.jobs.join();assert len(steps)==1 and not rip.discogs.queued,'at shutdown a step does not queue the next'

def test_identify_takes_the_owned_pressing():
    """AcoustID knows only the CD; the vinyl on the shelf is the same release group and carries the song, so it is used."""
    with tempfile.TemporaryDirectory() as tmp:
        rip=ripper(tmp);rip.acoustid='key';orig=(R.fingerprint,R.acoustid_lookup,R.mb_release)
        try:
            R.fingerprint=lambda path,start,seconds=120.:('FP',120)
            R.acoustid_lookup=lambda key,fp,dur:{'results':[{'score':.9,'id':'a','recordings':[{'id':'r1','title':'T2','releasegroups':[{'id':'rg-kid-a','title':'Kid A','releases':[rel('mb-cd','CD')]}]}]}]}
            R.mb_release=lambda mbid:album(mbid,'rg-kid-a')
            f=rip.home/'sides'/'s1.s24';f.write_bytes(b'\0'*6000);rip.side={'id':'s1','file':str(f),'album':None,'frames':200*R.FS}
            rip.identify(('s1',200.))
            assert rip.store['current_album']=='mb-kid-a' and rip.side['anchor']['index']==1 and rip.side['ident']['score']==.9,(rip.store['current_album'],rip.side)
        finally:R.fingerprint,R.acoustid_lookup,R.mb_release=orig

if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_'):fn();print('ok',name)
    print('PASS')
