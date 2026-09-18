#!/usr/bin/env python3
"""Measurement figures for the project page, drawn from real captures.

    python3 docs/figures.py <snapshot.raw> [outdir]

`snapshot.raw` is 10 s of the raw I2S stream from the live view (`/snapshot.raw`);
the frequency-response figure comes from the two `audio` bench runs. Output is SVG
sized for the dark surface of madsrudolph.dev.

Series colours are the two validated dark-surface categorical slots already used by
`pi/live.py`: blue = left, orange = right.
"""
from pathlib import Path
import re, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pi'))
import decimate as D

LEFT, RIGHT = '#3987e5', '#d95926'
INK, INK_2, MUTED = '#ffffff', '#c3c2b7', '#8f8888'
SURFACE, GRID = '#151312', 'rgba(255,255,255,0.09)'
RUNS = {'left': '20260918T093339Z-audio-a485477f', 'right': '20260918T094918Z-audio-78d57572'}

def esc(s): return str(s).replace('&', '&amp;').replace('<', '&lt;')

def head(w, h, title, sub):
    return [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{esc(title)}">',
            f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>',
            '<style>'
            f'.t{{font:600 17px system-ui,sans-serif;fill:{INK}}}'
            f'.s{{font:14px system-ui,sans-serif;fill:{MUTED}}}'
            f'.a{{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:{MUTED}}}'
            f'.lab{{font:600 13.5px system-ui,sans-serif}}'
            f'.note{{font:13px system-ui,sans-serif;fill:{INK_2}}}'
            '</style>',
            f'<text class="t" x="18" y="26">{esc(title)}</text>',
            f'<text class="s" x="18" y="45">{esc(sub)}</text>']

def legend(x, y, items, dashed_second=False):
    o = []
    for i, (name, colour) in enumerate(items):
        cx = x + i * 74
        if dashed_second and i == 1:
            o.append(f'<line x1="{cx}" y1="{y-6.5}" x2="{cx+16}" y2="{y-6.5}" stroke="{colour}" '
                     f'stroke-width="3" stroke-dasharray="5 3"/>')
        else:
            o.append(f'<rect x="{cx}" y="{y-8}" width="16" height="3" rx="1.5" fill="{colour}"/>')
        o.append(f'<text class="lab" x="{cx+22}" y="{y-2}" fill="{INK_2}">{name}</text>')
    return o

# ---------------------------------------------------------------- spectra
def log_bin(f, P, lo, hi, n=340):
    """Average a PSD into log-spaced bins so the trace reads as a curve, not a hairball."""
    edges = np.geomspace(lo, hi, n + 1)
    idx = np.digitize(f, edges) - 1
    out_f, out_p = [], []
    for k in range(n):
        m = idx == k
        if m.any():
            out_f.append(np.sqrt(edges[k] * edges[k+1])); out_p.append(P[m].mean())
    return np.array(out_f), np.array(out_p)

def shaping_figure(bits_l, bits_r, out):
    import importlib.util
    spec = importlib.util.spec_from_file_location('ab', ROOT / 'pi' / 'analyze_bitstream.py')
    ab = importlib.util.module_from_spec(spec); spec.loader.exec_module(ab)
    W, H = 900, 430
    X0, X1, Y0, Y1 = 66, 838, 78, 344
    LO, HI, TOP, BOT = 20., 768e3, -40., -145.
    o = head(W, H, 'Noise shaping of the 1-bit modulator streams',
             'Power density in dBFS/Hz, both inputs shorted. A third-order loop is flat in the audio band, then climbs.')
    px = lambda fr: X0 + (np.log10(fr) - np.log10(LO)) / (np.log10(HI) - np.log10(LO)) * (X1 - X0)
    py = lambda db: Y0 + (TOP - db) / (TOP - BOT) * (Y1 - Y0)
    # audio band
    o.append(f'<rect x="{px(20):.1f}" y="{Y0}" width="{px(20000)-px(20):.1f}" height="{Y1-Y0}" fill="#ffffff" opacity="0.035"/>')
    o.append(f'<text class="a" x="{(px(20)+px(20000))/2:.0f}" y="{Y0-8}" text-anchor="middle">audio band, 20 Hz – 20 kHz</text>')
    for db in range(-140, -39, 20):
        y = py(db)
        o.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{X0-9}" y="{y+4:.1f}" text-anchor="end">{db}</text>')
    for fr, lab in ((20,'20'),(100,'100'),(1e3,'1k'),(10e3,'10k'),(100e3,'100k'),(768e3,'768k')):
        x = px(fr)
        o.append(f'<line x1="{x:.1f}" y1="{Y0}" x2="{x:.1f}" y2="{Y1}" stroke="{GRID}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{x:.1f}" y="{Y1+18}" text-anchor="middle">{lab}</text>')
    o.append(f'<text class="a" x="{X0-9}" y="{Y0-8}" text-anchor="end">dBFS/Hz</text>')
    o.append(f'<text class="a" x="{(X0+X1)/2:.0f}" y="{Y1+36}" text-anchor="middle">frequency (Hz)</text>')
    for bits, colour, dash in ((bits_l, LEFT, ''), (bits_r, RIGHT, ' stroke-dasharray="5 3"')):
        P = ab.psd(bits); f = np.fft.rfftfreq(ab.N, 1 / ab.FS)
        fb, Pb = log_bin(f[1:], P[1:], LO, HI)
        fb, Pb = fb[:-2], Pb[:-2]        # the last log bins straddle Nyquist and turn up spuriously
        db = 10 * np.log10(np.maximum(Pb, 1e-30))
        pts = ' '.join(f'{px(a):.1f},{max(Y0, min(Y1, py(b))):.1f}' for a, b in zip(fb, db))
        o.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="1.8" '
                 f'stroke-linejoin="round" opacity="0.95"{dash}/>')
    o += legend(X1 - 150, Y0 - 12, [('Left', LEFT), ('Right', RIGHT)], dashed_second=True)
    ax, ay = px(26e3), py(-52)
    o.append(f'<text class="note" x="{ax:.0f}" y="{ay:.0f}">about +68 dB per decade</text>')
    o.append(f'<path d="M{ax+42:.0f} {ay+6:.0f} L{px(45e3):.0f} {py(-72):.0f}" stroke="{MUTED}" '
             f'stroke-width="1" fill="none" opacity="0.6"/>')
    o.append(f'<text class="note" x="18" y="{H-34}">The loop pushes quantisation noise out of the audio band; '
             f'the decimator then removes what is left above it.</text>')
    o.append(f'<text class="note" x="18" y="{H-14}" fill="{MUTED}">The two traces lie on top of each other \u2014 '
             f'right is dashed so both are visible. The spike near 13 kHz is the modulator\u2019s idle tone.</text>')
    o.append('</svg>')
    out.write_text('\n'.join(o) + '\n')
    return out

# ------------------------------------------------------- frequency response
def read_response(run):
    rows = []
    for line in (ROOT / 'assembly/bench/results' / run / 'summary.md').read_text().splitlines():
        m = re.match(r'\|\s*response\s*\|\s*response ([\d.]+) Hz\s*\|\s*([-\d.e]+)\s*\|', line)
        if m: rows.append((float(m.group(1)), float(m.group(2))))
    return sorted(rows)

def response_figure(out):
    W, H = 900, 380
    X0, X1, Y0, Y1 = 66, 838, 84, 290
    LO, HI, TOP, BOT = 18., 17500., 0.18, -0.18
    o = head(W, H, 'Frequency response, both channels',
             'Third-octave points at −20 dBFS, relative to 1 kHz. Full height is a third of a decibel.')
    px = lambda fr: X0 + (np.log10(fr) - np.log10(LO)) / (np.log10(HI) - np.log10(LO)) * (X1 - X0)
    py = lambda db: Y0 + (TOP - db) / (TOP - BOT) * (Y1 - Y0)
    o.append(f'<rect x="{X0}" y="{py(0.1):.1f}" width="{X1-X0}" height="{py(-0.1)-py(0.1):.1f}" fill="#ffffff" opacity="0.035"/>')
    o.append(f'<text class="a" x="{X1-6}" y="{py(0.1)-6:.1f}" text-anchor="end">±0.1 dB</text>')
    for db in (0.15, 0.1, 0.05, 0, -0.05, -0.1, -0.15):
        y = py(db); strong = db == 0
        o.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X1}" y2="{y:.1f}" stroke="{GRID}" '
                 f'stroke-width="{1.4 if strong else 1}"/>')
        o.append(f'<text class="a" x="{X0-9}" y="{y+4:.1f}" text-anchor="end">{db:+.2f}</text>')
    for fr, lab in ((20,'20'),(50,'50'),(100,'100'),(500,'500'),(1e3,'1k'),(5e3,'5k'),(10e3,'10k'),(16255,'16.3k')):
        x = px(fr)
        o.append(f'<line x1="{x:.1f}" y1="{Y0}" x2="{x:.1f}" y2="{Y1}" stroke="{GRID}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{x:.1f}" y="{Y1+18}" text-anchor="middle">{lab}</text>')
    o.append(f'<text class="a" x="{X0-9}" y="{Y0-8}" text-anchor="end">dB</text>')
    o.append(f'<text class="a" x="{(X0+X1)/2:.0f}" y="{Y1+36}" text-anchor="middle">frequency (Hz)</text>')
    spread = {}
    for name, colour, key in (('Left', LEFT, 'left'), ('Right', RIGHT, 'right')):
        rows = read_response(RUNS[key])
        spread[name] = max(g for _, g in rows) - min(g for _, g in rows)
        pts = ' '.join(f'{px(f):.1f},{max(Y0,min(Y1,py(g))):.1f}' for f, g in rows)
        o.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2" stroke-linejoin="round"/>')
        for f, g in rows:
            o.append(f'<circle cx="{px(f):.1f}" cy="{max(Y0,min(Y1,py(g))):.1f}" r="2.6" fill="{colour}" '
                     f'stroke="{SURFACE}" stroke-width="1"/>')
    o += legend(X1 - 150, Y0 - 14, [('Left', LEFT), ('Right', RIGHT)])
    rows_l = read_response(RUNS['left'])
    lo_f, hi_f = min(f for f, _ in rows_l), max(f for f, _ in rows_l)
    o.append(f'<text class="note" x="18" y="{H-32}">Left is flat within {spread["Left"]*1000:.0f} millidecibels '
             f'from {lo_f:.0f} Hz to {hi_f/1000:.1f} kHz, right within {spread["Right"]*1000:.0f}.</text>')
    o.append(f'<text class="note" x="18" y="{H-14}" fill="{MUTED}">The third-octave sweep stops at 16.3 kHz \u2014 '
             f'the next step would pass 20 kHz \u2014 so the top octave is not measured here.</text>')
    o.append('</svg>')
    out.write_text('\n'.join(o) + '\n')
    return out

# -------------------------------------------------------------- the bits
def bits_figure(bits_l, bits_r, out, n=192, start=int(1.2 * 1_536_000)):
    W, H = 900, 300
    X0, X1 = 66, 838
    o = head(W, H, 'What the converter actually outputs',
             f'The first {n} modulator bits of each channel, 1.536 million of them per second. Filled = 1.')
    cw = (X1 - X0) / n
    for row, (bits, colour, name) in enumerate(((bits_l, LEFT, 'Left'), (bits_r, RIGHT, 'Right'))):
        y = 96 + row * 86
        o.append(f'<text class="lab" x="18" y="{y+15}" fill="{INK_2}">{name}</text>')
        seg = bits[start:start + n]
        for i, b in enumerate(seg):
            if b:
                o.append(f'<rect x="{X0+i*cw:.2f}" y="{y}" width="{max(cw-0.6,0.6):.2f}" height="26" '
                         f'fill="{colour}" opacity="0.95"/>')
        o.append(f'<rect x="{X0}" y="{y}" width="{X1-X0}" height="26" fill="none" stroke="{GRID}" stroke-width="1"/>')
        d = seg.mean()
        o.append(f'<text class="a" x="{X1}" y="{y+45}" text-anchor="end">'
                 f'{d*100:.1f}% ones over this window</text>')
    o.append(f'<text class="a" x="{X0}" y="{96+86+45}">{n/1.536e6*1e6:.0f} microseconds of stream</text>')
    o.append(f'<text class="note" x="18" y="{H-34}">With the inputs shorted the stream is a fine, irregular hatch '
             f'sitting at half density: the loop is modulating.</text>')
    o.append(f'<text class="note" x="18" y="{H-14}">A broken loop looks completely different — long solid bars, '
             f'because it oscillates rail to rail instead of tracking the input.</text>')
    o.append('</svg>')
    out.write_text('\n'.join(o) + '\n')
    return out

def main():
    snap = Path(sys.argv[1] if len(sys.argv) > 1 else 'snapshot.raw')
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'docs/figures'
    outdir.mkdir(parents=True, exist_ok=True)
    words = np.concatenate(list(D.frames_from(str(snap))))
    L, R = D.split_bits(words)
    print(f'{len(L)/D.FS_MOD:.1f} s of stream; density L {L.mean():.4f} R {R.mean():.4f}')
    import importlib.util
    spec = importlib.util.spec_from_file_location('ab', ROOT / 'pi' / 'analyze_bitstream.py')
    ab = importlib.util.module_from_spec(spec); spec.loader.exec_module(ab)
    for name, b in (('left', L), ('right', R)):
        P = ab.psd(b); f = np.fft.rfftfreq(ab.N, 1 / ab.FS)
        band = (f >= 20) & (f <= 20000)
        inband = 10 * np.log10(ab.integrate(P, f, band))
        a = (f >= 28e3) & (f <= 32e3); c = (f >= 78e3) & (f <= 82e3)
        slope = (10*np.log10(P[c].mean()) - 10*np.log10(P[a].mean())) / np.log10(80/30)
        print(f'  {name:5s} in-band {inband:+7.2f} dBFS   shaping {slope:+5.1f} dB/decade'
              f'   {"<- idle-condition figures" if inband < -70 else "<- NOT the shorted-input condition"}')
    for p in (shaping_figure(L, R, outdir / 'noise-shaping.svg'),
              response_figure(outdir / 'frequency-response.svg'),
              bits_figure(L, R, outdir / 'modulator-bits.svg')):
        print(f'  wrote {p.relative_to(ROOT)}  ({p.stat().st_size/1024:.0f} kB)')

if __name__ == '__main__':
    main()
