#!/usr/bin/env python3
"""Offline tests of the ripper's decisions: identification, side cutting and repeat plays. No hardware, no network.

    python3 pi/test_ripper.py
"""
import json,sys,tempfile,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parent));import ripper as R

def release(mbid,title,tracks,fmt='12" Vinyl',match=None):
    """As AcoustID reports it: the medium lists only the track(s) that carry the matched recording."""
    i=len(tracks)-1 if match is None else match
    return {'id':mbid,'title':title,'medium_count':1,'mediums':[{'position':1,'format':fmt,'track_count':len(tracks),'tracks':[{'id':f't{i}','position':i+1,'title':tracks[i]}]}]}
def results():
    kid=release('rel-vinyl','Kid A',['Everything in Its Right Place','Kid A','The National Anthem'],match=1)
    cd=release('rel-cd','Kid A',['Everything in Its Right Place','Kid A','The National Anthem'],fmt='CD',match=1)
    comp=release('rel-comp','Alt Hits',['x']*30,fmt='CD')
    return [{'score':.93,'id':'a','recordings':[{'id':'rec-kid-a','title':'Kid A','artists':[{'name':'Radiohead'}],'releases':[cd,kid,comp]}]},
            {'score':.31,'id':'b','recordings':[{'id':'rec-other','title':'Other','releases':[release('rel-x','X',['Other'])]}]}]
def album(mbid,recs,lengths):
    return {'mbid':mbid,'title':'Kid A','artist':'Radiohead','date':'2000','discs':1,'next_track':0,'status':'selected',
            'tracks':[{'disc':1,'position':i+1,'number':str(i+1),'title':f'T{i+1}','length':l,'recording':r,'artist':'Radiohead'} for i,(r,l) in enumerate(zip(recs,lengths))]}

def test_rank():
    m=R.rank_releases(results())
    assert m[0]['release']=='rel-vinyl' and m[0]['vinyl'] and m[0]['position']==2,m[0]
    assert all(x['release']!='rel-x' for x in m),'low scores must be dropped'
    assert R.rank_releases(results(),current='rel-cd')[0]['release']=='rel-cd','the album in use comes first'

def make(tmp):
    rip=R.Ripper(tmp);rip.acoustid='key';rip.jobs=__import__('queue').Queue()
    R.fingerprint=lambda path,start,seconds=120.:('FP',120);R.acoustid_lookup=lambda key,fp,dur:{'status':'ok','results':results()}
    R.mb_release=lambda mbid:album(mbid,['rec-eirp','rec-kid-a','rec-anthem'],[251.,284.,351.])
    return rip

def side_file(rip,sid,seconds):
    """A raw side plus its envelope: music at -40 dB with 3 s gaps at the given times."""
    f=rip.home/'sides'/f'{sid}.s24';f.write_bytes(b'\0'*(int(seconds*R.FS)*6));n=int(seconds*10);env=np.full((n,3),-40.);env[:,:2]=.3
    return f,env

def test_identify_selects_album_and_track():
    with tempfile.TemporaryDirectory() as tmp:
        rip=make(tmp);f,_=side_file(rip,'s1',200)
        rip.side={'id':'s1','file':str(f),'album':None,'frames':200*R.FS}
        rip.identify(('s1',200.))
        assert rip.store['current_album']=='rel-vinyl' and rip.side['first']==1 and rip.side['ident']['status']=='ok',rip.side
        # a later side of the same record: the album in use is kept even though AcoustID ranks the CD first for it
        R.acoustid_lookup=lambda key,fp,dur:{'status':'ok','results':[{'score':.9,'id':'c','recordings':[{'id':'rec-anthem','title':'The National Anthem','releases':[release('rel-cd','Kid A',['a','b','The National Anthem'],fmt='CD')]}]}]}
        rip.side={'id':'s2','file':str(f),'album':None,'frames':200*R.FS};rip.identify(('s2',200.))
        assert rip.side['album']=='rel-vinyl' and rip.side['first']==2,rip.side
        # a different record while an album is in progress: the old one is sent as it is
        rip.store['albums']['rel-vinyl']['status']='in progress'
        R.acoustid_lookup=lambda key,fp,dur:{'status':'ok','results':[{'score':.9,'id':'d','recordings':[{'id':'rec-new','title':'New','releases':[release('rel-new','New Album',['New'])]}]}]}
        R.mb_release=lambda mbid:album(mbid,['rec-new'],[300.])
        rip.side={'id':'s3','file':str(f),'album':None,'frames':200*R.FS};rip.identify(('s3',200.))
        assert rip.store['current_album']=='rel-new' and ('finalize','rel-vinyl') in list(rip.jobs.queue),list(rip.jobs.queue)

def test_no_key():
    with tempfile.TemporaryDirectory() as tmp:
        rip=make(tmp);rip.acoustid=None;f,_=side_file(rip,'s1',200);rip.side={'id':'s1','file':str(f),'album':None,'frames':200*R.FS}
        rip.identify(('s1',200.));assert rip.side['ident']=={'status':'no key'} and rip.store['current_album'] is None

def test_duration_from_envelope_and_scan():
    """AcoustID answers only for durations near the real track length: the closed-side path measures it, the scan finds it."""
    with tempfile.TemporaryDirectory() as tmp:
        rip=make(tmp);asked=[];R.time.sleep=lambda s:None
        R.acoustid_lookup=lambda key,fp,dur:(asked.append(dur) or {'status':'ok','results':results() if abs(dur-251)<=10 else []})
        f,env=side_file(rip,'s1',640);env[:5,2]=-80.;env[2520:2550,2]=-80.;env[6300:,2]=-80.;np.save(f.with_suffix('.env.npy'),env)     # music from 0.5 s, gap at 252 s
        side={'id':'s1','started':time.time(),'file':str(f),'frames':640*R.FS,'gaps':[],'album':None,'status':'recorded','seconds':640.,'peak':.3,'tracks':[]}
        rip.store['sides'].append(side);segs=rip.track_segments(side);assert len(segs)==2 and abs(segs[0][0])<.6 and abs(segs[0][1][0][0]-252)<1 and abs(segs[1][0]-255)<1,segs
        rip.identify(('s1','closed'));assert side['ident']['status']=='ok' and len(asked)==1 and abs(asked[0]-253.5)<1,(side['ident'],asked)
        # an unknown first track (an intro): the second track, 255-630 s, is tried next and found by its own length
        asked.clear();R.acoustid_lookup=lambda key,fp,dur:(asked.append(dur) or {'status':'ok','results':results() if abs(dur-375)<=10 else []})
        side['ident']=None;rip.identify(('s1','closed'));assert side['ident']['status']=='ok' and 370<=asked[-1]<=385 and len(asked)==4,(side['ident'],asked)
        asked.clear();R.acoustid_lookup=lambda key,fp,dur:(asked.append(dur) or {'status':'ok','results':results() if abs(dur-251)<=10 else []});side2={**side,'id':'s2','ident':None};rip.side=side2;rip.identify(('s2',None));assert side2['ident']['status']=='ok' and asked[-1]==250 and len(asked)==14,asked

def test_split_uses_first_and_trashes_repeats():
    with tempfile.TemporaryDirectory() as tmp:
        rip=make(tmp);a=album('rel-vinyl',['r1','r2','r3'],[251.,284.,351.]);rip.store['albums']['rel-vinyl']=a;rip.store['current_album']='rel-vinyl'
        f,env=side_file(rip,'s1',640);env[2840:2870,2]=-80.;env[6300:,2]=-80.;np.save(f.with_suffix('.env.npy'),env)      # gap at 284-287 s, silence after 630 s
        side={'id':'s1','started':time.time(),'file':str(f),'frames':640*R.FS,'gaps':[],'album':'rel-vinyl','status':'recorded','seconds':640.,'peak':.3,'tracks':[],'first':1}
        rip.store['sides'].append(side);rip.split_side('s1')
        assert [t['index'] for t in side['tracks']]==[1,2] and abs(side["tracks"][0]["end"]-285.5)<1.,side['tracks']
        assert a['next_track']==3 and a['status']=='in progress'     # track 1 was never played
        # the same side again: it must not be assigned twice
        g,_=side_file(rip,'s2',640);np.save(g.with_suffix('.env.npy'),env)
        again={**side,'id':'s2','file':str(g),'tracks':[]};rip.store['sides'].append(again);rip.split_side('s2')
        assert again not in rip.store['sides'] and (rip.home/'trash'/'s2.s24').exists() and a['next_track']==3
        # a restart from track 1 that runs through track 3: it takes over the tracks the shorter side had, which is then trashed
        h,env3=side_file(rip,'s3',900);env3[2500:2540,2]=-80.;env3[5340:5380,2]=-80.;env3[8860:,2]=-80.;np.save(h.with_suffix('.env.npy'),env3)
        full={**side,'id':'s3','file':str(h),'frames':900*R.FS,'seconds':900.,'tracks':[],'first':0};rip.store['sides'].append(full);rip.split_side('s3')
        assert [t['index'] for t in full['tracks']]==[0,1,2] and side not in rip.store['sides'] and a['status']=='complete',(full['tracks'],a)

if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_'):fn();print('ok',name)
    print('PASS')
