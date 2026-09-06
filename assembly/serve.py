#!/usr/bin/env python3
"""Serve the assembly guide on loopback only, without external dependencies."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8080);a=p.parse_args()
results=Path(__file__).resolve().parent/'bench/results'
results.mkdir(parents=True,exist_ok=True)
index=results/'index.json'
if not index.exists():index.write_text('[]\n')
print(f'Assembly bench: http://localhost:{a.port}',flush=True)
ThreadingHTTPServer(('127.0.0.1',a.port),partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).resolve().parent))).serve_forever()
