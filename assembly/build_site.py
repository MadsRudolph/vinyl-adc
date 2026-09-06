#!/usr/bin/env python3
"""Build the public, static assembly site without installers or private run files."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'site-dist'

def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for pattern in ('*.html', '*.css', '*.js', 'README.md', '_headers'):
        for source in ROOT.glob(pattern):
            shutil.copy2(source, OUT / source.name)
    for directory in ('generated', 'sessions'):
        shutil.copytree(ROOT / directory, OUT / directory)
    (OUT / 'bench' / 'results').mkdir(parents=True)
    for name in ('plans.json', 'limits.json', 'README.md'):
        shutil.copy2(ROOT / 'bench' / name, OUT / 'bench' / name)
    # Local SDK captures are not automatically published or fabricated as PASSes.
    (OUT / 'bench' / 'results' / 'index.json').write_text('[]\n')
    (OUT / 'downloads').mkdir()
    shutil.copy2(ROOT / 'downloads' / 'README.md', OUT / 'downloads' / 'README.md')
    (OUT / '404.html').write_text('<!doctype html><meta charset="utf-8"><title>Not found</title><h1>Page not found</h1><a href="/">Return to the assembly guide</a>')
    (OUT / 'robots.txt').write_text('User-agent: *\nAllow: /\n')
    total = sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    print(json.dumps({'output': str(OUT), 'bytes': total, 'manual_session': '2026-09-06', 'instrument_control': False}))

if __name__ == '__main__':
    build()
