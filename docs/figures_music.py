#!/usr/bin/env python3
"""Two figures showing real music through the converter, for the project page.

    python3 docs/figures_music.py <excerpt.wav> <idle-snapshot.raw> [outdir]

`excerpt.wav` is a 48 kHz stereo cut from the ripper's FLAC (see media/ab/make_ab.py);
`idle-snapshot.raw` is 10 s of the raw modulator stream with the inputs shorted, which
is decimated here exactly as the ripper does it so the two spectra are comparable.

Outputs are analysis of the recording - a spectrogram and a spectrum - and can be
published; the recording itself cannot.
"""
from pathlib import Path
import base64, io, sys, wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pi'))
import decimate as D

FS = 48000
LEFT, RIGHT = '#3987e5', '#d95926'
INK, INK_2, MUTED = '#ffffff', '#c3c2b7', '#8f8888'
SURFACE, GRID = '#151312', 'rgba(255,255,255,0.09)'
FMIN, FMAX = 20., 20000.

def esc(s): return str(s).replace('&', '&amp;').replace('<', '&lt;')

def head(w, h, title, sub):
    return [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" role="img" aria-label="{esc(title)}">',
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

def read_wav(path):
    with wave.open(str(path)) as w:
        n = w.getnframes(); x = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, w.getnchannels()).T
    return x.astype(np.float64) / 32768.

def idle_audio(raw):
    """Decimate the shorted-input capture the way the ripper does, return (2, n) at 48 kHz."""
    h = D.compensating_fir(); chains = [(D.Cic(), D.FirDecimator(h)) for _ in range(2)]; out = [[], []]
    for words in D.frames_from(str(raw)):
        for ch, bits in enumerate(D.split_bits(words)):
            cic, fir = chains[ch]; out[ch].append(fir.process(cic.process(bits.astype(np.int8) * 2 - 1)))
    a = np.vstack([np.concatenate(c) for c in out])[:, D.SETTLE:]
    return a - a.mean(axis=1, keepdims=True)

def avg_spectrum(x, n=4096):
    """Mean power per bin, Hann window, in the same dBFS-per-bin units as the bench (full-scale sine sums to 1)."""
    w = np.hanning(n); k = len(x) // n; P = np.zeros(n // 2 + 1)
    for i in range(k):
        X = np.fft.rfft(x[i*n:(i+1)*n] * w) / w.sum() * 2; P += np.abs(X) ** 2 / 1.5
    return np.fft.rfftfreq(n, 1 / FS), P / max(k, 1)

def log_bin(f, P, n=300):
    edges = np.geomspace(FMIN, FMAX, n + 1); idx = np.digitize(f, edges) - 1
    fo, po = [], []
    for k in range(n):
        m = idx == k
        if m.any(): fo.append(np.sqrt(edges[k] * edges[k+1])); po.append(P[m].mean())
    return np.array(fo), np.array(po)

# ---------------------------------------------------------------- spectrogram
def ramp(v):
    """Single-hue sequential ramp for a dark surface: quiet = the surface, loud = bright blue, peaks = near white."""
    stops = np.array([[0x15, 0x13, 0x12], [0x1b, 0x3a, 0x6a], [0x39, 0x87, 0xe5], [0xa9, 0xcd, 0xf5], [0xff, 0xff, 0xff]]) / 255.
    pos = np.array([0., .45, .74, .91, 1.])
    v = np.clip(v, 0, 1)
    return np.stack([np.interp(v, pos, stops[:, c]) for c in range(3)], axis=-1)

def spectrogram_figure(x, out, seconds):
    from PIL import Image
    n, hop = 2048, 1024                                  # ~21 ms columns: about 1100 of them for 24 s
    w = np.hanning(n); cols = (len(x) - n) // hop
    R = 320; rows_f = np.geomspace(FMIN, FMAX, R + 1)     # log-spaced frequency rows
    f = np.fft.rfftfreq(n, 1 / FS); idx = np.digitize(f, rows_f) - 1
    centres = np.sqrt(rows_f[:-1] * rows_f[1:]); nearest = np.array([int(np.argmin(np.abs(f - fc))) for fc in centres])
    members = [np.flatnonzero(idx == r) for r in range(R)]  # bins inside each row; empty below ~300 Hz at this FFT size
    img = np.empty((R, cols))
    for c in range(cols):
        X = np.fft.rfft(x[c*hop:c*hop+n] * w) / w.sum() * 2; db = 10 * np.log10(np.abs(X) ** 2 / 1.5 + 1e-30)
        for r in range(R):
            m = members[r]; img[r, c] = db[m].max() if len(m) else db[nearest[r]]   # a row narrower than a bin shows that bin
    lo, hi = -100., -30.
    rgb = (ramp((img - lo) / (hi - lo))[::-1] * 255).astype(np.uint8)   # top row = highest frequency
    buf = io.BytesIO(); Image.fromarray(rgb).quantize(colors=256).save(buf, format='PNG', optimize=True)
    png = base64.b64encode(buf.getvalue()).decode()

    W, H = 900, 470; X0, X1, Y0, Y1 = 66, 838, 78, 388
    o = head(W, H, 'Twenty-four seconds of a record, through the converter',
             'Everything in Its Right Place, 2:05 to 2:29, left channel of the ripper’s 48 kHz output. Level per 2048-point FFT bin.')
    o.append(f'<image x="{X0}" y="{Y0}" width="{X1-X0}" height="{Y1-Y0}" preserveAspectRatio="none" '
             f'xlink:href="data:image/png;base64,{png}"/>')
    py = lambda fr: Y1 - (np.log10(fr) - np.log10(FMIN)) / (np.log10(FMAX) - np.log10(FMIN)) * (Y1 - Y0)
    for fr, lab in ((50,'50'),(100,'100'),(200,'200'),(500,'500'),(1e3,'1k'),(2e3,'2k'),(5e3,'5k'),(10e3,'10k'),(20e3,'20k')):
        y = py(fr)
        o.append(f'<line x1="{X0-4}" y1="{y:.1f}" x2="{X0}" y2="{y:.1f}" stroke="{MUTED}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{X0-8}" y="{y+4:.1f}" text-anchor="end">{lab}</text>')
    for t in range(0, int(seconds) + 1, 4):
        x = X0 + t / seconds * (X1 - X0)
        o.append(f'<line x1="{x:.1f}" y1="{Y1}" x2="{x:.1f}" y2="{Y1+4}" stroke="{MUTED}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{x:.1f}" y="{Y1+18}" text-anchor="middle">{t} s</text>')
    o.append(f'<text class="a" x="{X0-8}" y="{Y0-8}" text-anchor="end">Hz</text>')
    # colour key
    kx, ky, kw = X1 - 200, Y1 + 30, 200
    o.append('<defs><linearGradient id="k" x1="0" x2="1" y1="0" y2="0">' +
             ''.join(f'<stop offset="{p*100:.0f}%" stop-color="rgb({int(c[0]*255)},{int(c[1]*255)},{int(c[2]*255)})"/>'
                     for p, c in zip(np.linspace(0, 1, 9), ramp(np.linspace(0, 1, 9)))) + '</linearGradient></defs>')
    o.append(f'<rect x="{kx}" y="{ky}" width="{kw}" height="8" fill="url(#k)" rx="2"/>')
    o.append(f'<text class="a" x="{kx}" y="{ky+22}">{lo:.0f}</text>')
    o.append(f'<text class="a" x="{kx+kw}" y="{ky+22}" text-anchor="end">{hi:.0f} dBFS</text>')
    o.append(f'<text class="note" x="18" y="{H-34}">The electric piano’s chords are the horizontal bands; the bass is the bright floor under 100 Hz.</text>')
    o.append(f'<text class="note" x="18" y="{H-14}" fill="{MUTED}">This rip was made before the right-channel repair, so the ripper fell back to mono: left copied to both sides.</text>')
    o.append('</svg>'); out.write_text('\n'.join(o) + '\n'); return out

# ------------------------------------------------- music against the noise floor
def floor_figure(music, idle, out):
    W, H = 900, 430; X0, X1, Y0, Y1 = 66, 838, 78, 344
    TOP, BOT = -20., -150.
    o = head(W, H, 'The record against the converter’s own noise floor',
             'Average spectrum of the same 24 s (left channel) over the idle output with both inputs shorted. Same FFT, same units.')
    px = lambda fr: X0 + (np.log10(fr) - np.log10(FMIN)) / (np.log10(FMAX) - np.log10(FMIN)) * (X1 - X0)
    py = lambda db: Y0 + (TOP - db) / (TOP - BOT) * (Y1 - Y0)
    for db in range(-140, -19, 20):
        y = py(db); o.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{X0-9}" y="{y+4:.1f}" text-anchor="end">{db}</text>')
    for fr, lab in ((20,'20'),(50,'50'),(100,'100'),(500,'500'),(1e3,'1k'),(5e3,'5k'),(10e3,'10k'),(20e3,'20k')):
        x = px(fr); o.append(f'<line x1="{x:.1f}" y1="{Y0}" x2="{x:.1f}" y2="{Y1}" stroke="{GRID}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{x:.1f}" y="{Y1+18}" text-anchor="middle">{lab}</text>')
    o.append(f'<text class="a" x="{X0-9}" y="{Y0-8}" text-anchor="end">dBFS/bin</text>')
    o.append(f'<text class="a" x="{(X0+X1)/2:.0f}" y="{Y1+36}" text-anchor="middle">frequency (Hz)</text>')
    f, Pm = avg_spectrum(music); _, Pi = avg_spectrum(idle)
    fm, pm = log_bin(f[1:], Pm[1:]); fi, pi = log_bin(f[1:], Pi[1:])
    dm, di = 10*np.log10(pm+1e-30), 10*np.log10(pi+1e-30)
    # the gap, shaded
    up = ' '.join(f'{px(a):.1f},{max(Y0,min(Y1,py(b))):.1f}' for a, b in zip(fm, dm))
    dn = ' '.join(f'{px(a):.1f},{max(Y0,min(Y1,py(b))):.1f}' for a, b in zip(fi[::-1], di[::-1]))
    o.append(f'<polygon points="{up} {dn}" fill="{LEFT}" opacity="0.10"/>')
    o.append(f'<polyline points="{up}" fill="none" stroke="{LEFT}" stroke-width="2" stroke-linejoin="round"/>')
    pts_i = ' '.join(f'{px(a):.1f},{max(Y0,min(Y1,py(b))):.1f}' for a, b in zip(fi, di))
    o.append(f'<polyline points="{pts_i}" fill="none" stroke="{MUTED}" stroke-width="1.6" stroke-linejoin="round"/>')
    # the gap at 1 kHz, in numbers
    k1 = int(np.argmin(np.abs(fm - 1000))); gap = dm[k1] - di[k1]
    o.append(f'<line x1="{px(1000):.1f}" y1="{py(dm[k1]):.1f}" x2="{px(1000):.1f}" y2="{py(di[k1]):.1f}" stroke="{INK_2}" stroke-width="1" stroke-dasharray="3 3"/>')
    o.append(f'<text class="note" x="{px(1000)+8:.0f}" y="{(py(dm[k1])+py(di[k1]))/2:.0f}">{gap:.0f} dB between the music and the floor at 1 kHz</text>')
    o.append(f'<rect x="{X1-330}" y="{Y0-22}" width="16" height="3" rx="1.5" fill="{LEFT}"/><text class="lab" x="{X1-308}" y="{Y0-16}" fill="{INK_2}">the record</text>')
    o.append(f'<rect x="{X1-210}" y="{Y0-22}" width="16" height="3" rx="1.5" fill="{MUTED}"/><text class="lab" x="{X1-188}" y="{Y0-16}" fill="{INK_2}">converter idle, inputs shorted</text>')
    o.append(f'<text class="note" x="18" y="{H-34}">The shaded band is the converter\u2019s headroom: everything in it is the record, not the electronics. Its own floor above 10 kHz is the groove.</text>')
    o.append(f'<text class="note" x="18" y="{H-14}" fill="{MUTED}">Both spectra: 4096-point Hann FFTs averaged over the excerpt, dBFS per bin, where a full-scale sine reads 0.</text>')
    o.append('</svg>'); out.write_text('\n'.join(o) + '\n'); return out

def main():
    wav, raw = Path(sys.argv[1]), Path(sys.argv[2])
    outdir = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / 'docs/figures'; outdir.mkdir(parents=True, exist_ok=True)
    x = read_wav(wav); music = x[0]; seconds = len(music) / FS
    print(f'excerpt {seconds:.1f} s, L/R correlation {np.corrcoef(x[0], x[1])[0,1]:+.3f}')
    idle = idle_audio(raw)[0]
    print(f'idle {len(idle)/FS:.1f} s decimated, rms {20*np.log10(np.sqrt((idle**2).mean())):.1f} dBFS')
    for p in (spectrogram_figure(music, outdir / 'music-spectrogram.svg', seconds),
              floor_figure(music, idle, outdir / 'music-vs-floor.svg')):
        print(f'  wrote {p.relative_to(ROOT)}  ({p.stat().st_size/1024:.0f} kB)')

if __name__ == '__main__':
    main()
