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
        rip.identify('s1')
        assert rip.store['current_album']=='rel-vinyl' and rip.side['first']==1 and rip.side['ident']['status']=='ok',rip.side
        # a later side of the same record: the album in use is kept even though AcoustID ranks the CD first for it
        R.acoustid_lookup=lambda key,fp,dur:{'status':'ok','results':[{'score':.9,'id':'c','recordings':[{'id':'rec-anthem','title':'The National Anthem','releases':[release('rel-cd','Kid A',['a','b','The National Anthem'],fmt='CD')]}]}]}
        rip.side={'id':'s2','file':str(f),'album':None,'frames':200*R.FS};rip.identify('s2')
        assert rip.side['album']=='rel-vinyl' and rip.side['first']==2,rip.side
        # a different record while an album is in progress: the old one is sent as it is
        rip.store['albums']['rel-vinyl']['status']='in progress'
        R.acoustid_lookup=lambda key,fp,dur:{'status':'ok','results':[{'score':.9,'id':'d','recordings':[{'id':'rec-new','title':'New','releases':[release('rel-new','New Album',['New'])]}]}]}
        R.mb_release=lambda mbid:album(mbid,['rec-new'],[300.])
        rip.side={'id':'s3','file':str(f),'album':None,'frames':200*R.FS};rip.identify('s3')
        assert rip.store['current_album']=='rel-new' and ('finalize','rel-vinyl') in list(rip.jobs.queue),list(rip.jobs.queue)

def test_no_key():
    with tempfile.TemporaryDirectory() as tmp:
        rip=make(tmp);rip.acoustid=None;f,_=side_file(rip,'s1',200);rip.side={'id':'s1','file':str(f),'album':None,'frames':200*R.FS}
        rip.identify('s1');assert rip.side['ident']=={'status':'no key'} and rip.store['current_album'] is None

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

if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_'):fn();print('ok',name)
    print('PASS')
