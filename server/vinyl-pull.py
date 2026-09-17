#!/usr/bin/env python3
"""Fetch finished vinyl rips from the Vinyl ADC Pi into the Jellyfin music library.

Runs on the Proxmox host as root from vinyl-pull.timer (same posture as autorip: LAN only, no auth).
The Pi publishes finished albums at /outbox.json; this script downloads each file next to its final place,
checks size and SHA-256, moves it in, fixes ownership and tells the Pi the album has arrived.
Strictly additive: it never deletes anything and never overwrites a file that differs.
Jellyfin's Music library already watches /srv/media/music with real-time monitoring, so albums show up by themselves.
"""
import hashlib,json,os,re,sys,urllib.parse,urllib.request
PI=os.environ.get('VINYL_PI','http://192.168.50.137:8091').rstrip('/')
DEST=os.environ.get('VINYL_DEST','/srv/media/music/Vinyl');LIBRARY=os.environ.get('VINYL_LIBRARY_ROOT','/srv/media/music')
OK=re.compile(r"^[^/\\\x00-\x1f]{1,180}$")

def fetch(path,data=None):
    req=urllib.request.Request(PI+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    return urllib.request.urlopen(req,timeout=60)
def clean(part):
    if not OK.match(part) or part.startswith('.') or part in ('..','.'):raise ValueError(f'refusing unsafe name {part!r}')
    return part
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def main():
    try:outbox=json.load(fetch('/outbox.json'))
    except Exception as e:print(f'Pi not reachable at {PI}: {e}');return 0
    owner=os.stat(LIBRARY);os.makedirs(DEST,exist_ok=True);os.chown(DEST,owner.st_uid,owner.st_gid)
    for album in outbox:
        parts=[clean(p) for p in album['folder'].split('/')]
        if not 1<=len(parts)<=3:raise ValueError('unexpected folder depth')
        folder=DEST
        for p in parts:
            folder=os.path.join(folder,p);os.makedirs(folder,exist_ok=True);os.chown(folder,owner.st_uid,owner.st_gid);os.chmod(folder,0o755)
        complete=True
        for f in album['files']:
            name=clean(f['name']);final=os.path.join(folder,name)
            if os.path.exists(final):
                if sha(final)==f['sha256']:continue
                print(f'KEEPING existing, different file {final}; not overwriting');complete=False;continue
            tmp=os.path.join(folder,'.incoming-'+name)
            with fetch(f"/outbox/{album['album']}/{urllib.parse.quote(name)}") as r,open(tmp,'wb') as out:
                while True:
                    block=r.read(1<<20)
                    if not block:break
                    out.write(block)
            if os.path.getsize(tmp)!=f['size'] or sha(tmp)!=f['sha256']:
                os.remove(tmp);print(f'checksum mismatch for {name}; will retry next run');complete=False;continue
            os.chown(tmp,owner.st_uid,owner.st_gid);os.chmod(tmp,0o644);os.replace(tmp,final);print(f'fetched {final}')
        if complete:
            fetch('/outbox/ack',{'album':album['album']}).read();print(f"album complete: {album['folder']}")
    return 0
if __name__=='__main__':sys.exit(main())
