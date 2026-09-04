"""Offline check of site/index.html: every referenced asset exists relative to
site/, nothing is loaded from the network, no <script>, and the images are the
expected 1920x1080 PNGs.

    python site/check_site.py
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
html = (SITE / "index.html").read_text(encoding="utf-8")

ok = True
refs = re.findall(r'(?:src|href)="([^"]+)"', html)
external = [r for r in refs if re.match(r"^(https?:)?//", r)]
if external:
    print("EXTERNAL references found:", external)
    ok = False
if re.search(r"<script", html, re.I):
    print("<script> tag found")
    ok = False
if re.search(r"@import|url\(\s*['\"]?https?:", html, re.I):
    print("external CSS/font reference found")
    ok = False

for r in refs:
    if r.startswith("#"):
        continue
    p = SITE / r
    if not p.exists():
        print("MISSING:", r)
        ok = False
        continue
    if p.suffix.lower() == ".png":
        with p.open("rb") as fh:
            sig = fh.read(8)
            fh.read(4)
            ihdr = fh.read(4)
            w, h = struct.unpack(">II", fh.read(8))
        good = sig == b"\x89PNG\r\n\x1a\n" and ihdr == b"IHDR"
        print(f"{r}: {w}x{h} PNG {'ok' if good and (w, h) == (1920, 1080) else 'UNEXPECTED'} ({p.stat().st_size // 1024} kB)")
        ok &= good and (w, h) == (1920, 1080)

size = (SITE / "index.html").stat().st_size
print(f"index.html {size} bytes, {len(refs)} references, viewport meta: {'viewport' in html}, "
      f"prefers-color-scheme: {'prefers-color-scheme' in html}")
print("RESULT:", "SITE OK" if ok else "SITE BROKEN")
sys.exit(0 if ok else 1)
