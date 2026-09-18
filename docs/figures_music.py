#!/usr/bin/env python3
"""Two figures showing real music through the converter, for the project page.

    python3 docs/figures_music.py <excerpt.wav> <idle-snapshot.raw> [outdir]

`excerpt.wav` is a 48 kHz stereo cut from the ripper's FLAC (see media/ab/make_ab.py);
`idle-snapshot.raw` is 10 s of the raw modulator stream with the inputs shorted, which
is decimated here exactly as the ripper does it so the two spectra are comparable.

Outputs are analysis of the recording - a spectrogram with a loudest-note lane and a
beat lane, a spectrum against the idle floor, and the data the page's interactive
version draws from - and can be published; the recording itself cannot.
"""
from pathlib import Path
import base64, io, json, sys, wave
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

WINDOWS = ((8192, 250.), (4096, 1000.), (2048, FMAX + 1))   # FFT length, and the highest row centre it serves
HOP, ROWS = 1024, 320                                        # ~21 ms columns, 32 rows per octave
NOTE_NAMES = ['C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B']

def note_name(f):
    m = int(round(69 + 12 * np.log2(f / 440.))); cents = int(round(1200 * np.log2(f / (440. * 2 ** ((m - 69) / 12)))))
    return f"{NOTE_NAMES[m % 12]}{m // 12 - 1}", cents

def spectrogram_data(x):
    """Log-frequency dB image, ROWS from FMIN to FMAX by one column per HOP samples, and the STFTs it came from.

    Three window lengths, all centred on the same instants: 171 ms below 250 Hz so the bass notes resolve
    (a 43 ms window smears them into 23 Hz blocks), 85 ms up to 1 kHz, and 43 ms above, where the hits live.
    Also the passage's own average level at each frequency, smoothed over 0.4 octave: what a note or a hit
    stands out *from*, and the reference for the page's default view."""
    cols = (len(x) - 2048) // HOP; pad = 4096; xp = np.pad(x, pad)
    fade = int(0.01 * FS); ramp_in = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fade))   # the excerpt is a hard cut; without
    xp[pad:pad + fade] *= ramp_in; xp[pad + len(x) - fade:pad + len(x)] *= ramp_in[::-1]   # this its edges splatter
    rows_f = np.geomspace(FMIN, FMAX, ROWS + 1); centres = np.sqrt(rows_f[:-1] * rows_f[1:])
    img = np.empty((ROWS, cols)); stft = {}; lo_f = 0.
    for n, hi_f in WINDOWS:
        w = np.hanning(n); f = np.fft.rfftfreq(n, 1 / FS); M = np.empty((len(f), cols))
        for c in range(cols):
            ctr = c * HOP + 1024 + pad; X = np.fft.rfft(xp[ctr - n // 2:ctr + n // 2] * w) / w.sum() * 2
            M[:, c] = 10 * np.log10(np.abs(X) ** 2 / 1.5 + 1e-30)
        idx = np.digitize(f, rows_f) - 1
        for r in np.flatnonzero((centres > lo_f) & (centres <= hi_f)):
            m = np.flatnonzero(idx == r)             # bins inside the row; a row narrower than a bin shows the nearest bin
            img[r] = M[m].max(axis=0) if len(m) else M[int(np.argmin(np.abs(f - centres[r])))]
        stft[n] = (f, M); lo_f = hi_f
    med = np.median(img, axis=1); k = 13
    env = np.convolve(np.pad(med, (6, 6), mode='edge'), np.ones(k) / k, mode='valid')
    return dict(img=img, env=env, rows_f=rows_f, centres=centres, hop=HOP, cols=cols, stft=stft,
                lo=-100., hi=-10., rel_lo=-20., rel_hi=20.)

def features(x, sg):
    """What the picture is made of, read from the data rather than asserted: the sustained bands and their
    notes, the hits, which note is loudest at each moment, and where each kind of thing is at its clearest."""
    img, env, hop, cols, centres = sg['img'], sg['env'], sg['hop'], sg['cols'], sg['centres']
    # sustained bands: peaks of the time-averaged spectrum between 40 Hz and 1.5 kHz, with their notes
    f, P = avg_spectrum(x, 4096); db = 10 * np.log10(P + 1e-30)
    lo_i, hi_i = np.searchsorted(f, 40), np.searchsorted(f, 1500); bands = []
    for i in range(lo_i + 2, hi_i - 2):
        if db[i] >= db[i-1] and db[i] >= db[i+1] and db[i] > db[i-2] and db[i] > db[i+2] and db[i] > np.median(db[lo_i:hi_i]) + 12:
            a, b, c = db[i-1], db[i], db[i+1]; d = 0.5 * (a - c) / (a - 2*b + c) if (a - 2*b + c) else 0.   # parabolic peak
            fp = float(f[i] + d * (f[1] - f[0])); name, cents = note_name(fp)
            bands.append(dict(hz=round(fp, 1), db=round(float(b), 1), note=name, cents=cents))
    bands = sorted(bands, key=lambda z: -z['db'])[:10]
    # hits: positive spectral flux of the 2-8 kHz rows between neighbouring columns; a hit is a peak 150 ms clear of the last
    sel = (centres >= 2000) & (centres <= 8000)
    flux = np.concatenate(([0.], np.maximum(np.diff(img[sel], axis=1), 0).sum(axis=0)))
    thr = flux.mean() + 2.0 * flux.std(); min_gap = int(0.15 * FS / hop); onsets = []; last = -min_gap
    for c in range(1, len(flux) - 1):
        if flux[c] > thr and flux[c] >= flux[c-1] and flux[c] >= flux[c+1] and c - last >= min_gap:
            onsets.append(round(c * hop / FS, 3)); last = c
    flux_n = np.clip(flux / np.percentile(flux, 99), 0, 1)
    # loudest note: power in the 171 ms window's bins between 60 Hz and 2 kHz, summed per note name, per column;
    # scaled to the strongest note in the column, and dimmed where the whole column is quiet
    f8, M = sg['stft'][8192]; sel = (f8 >= 60) & (f8 <= 2000); Pw = 10 ** (M[sel] / 10)
    pc = (np.round(12 * np.log2(f8[sel] / 440.)) + 69).astype(int) % 12
    C = np.stack([Pw[pc == k].sum(axis=0) for k in range(12)])
    strength = 10 * np.log10(C.max(axis=0) + 1e-30); gate = np.clip((strength - (strength.max() - 25)) / 25, 0, 1)
    chroma = C / np.maximum(C.max(axis=0), 1e-30) * gate
    # where each kind of thing is clearest (a 0.5 s average), so the page can play it on request
    smooth = lambda v: np.convolve(v, np.ones(23) / 23, mode='same')
    edge = int(0.5 * FS / hop)                                   # not the first or last half second
    peak_t = lambda v: round(float((edge + np.argmax(smooth(v)[edge:-edge])) * hop / FS), 2)
    band_rows = [int(np.argmin(np.abs(centres - b['hz']))) for b in bands]
    moments = dict(
        bands=peak_t((img[band_rows] - env[band_rows][:, None]).mean(axis=0)) if bands else 0.,
        hits=max(onsets, key=lambda t: flux_n[int(round(t * FS / hop))]) if onsets else 0.,
        bass=peak_t(img[centres < 90].mean(axis=0)),
        highs=peak_t(img[centres >= 6000].mean(axis=0)))
    return dict(bands=bands, onsets=onsets, flux=flux_n, chroma=chroma, moments=moments)

# shared layout of the static figure and the page's canvas: the plot, a lane for the loudest note, a lane for the beat
W, H = 900, 524; X0, X1 = 66, 812; Y0, Y1 = 78, 314; CY0, CY1 = 330, 450; HY0, HY1 = 464, 494

def spectrogram_figure(sg, feat, out, seconds):
    """The no-JS fallback: the same picture the page draws, as an SVG with the two lanes and the labels."""
    from PIL import Image
    img, env = sg['img'], sg['env']; lo, hi = sg['rel_lo'], sg['rel_hi']
    def png(rgb):
        buf = io.BytesIO(); Image.fromarray(rgb).quantize(colors=256).save(buf, format='PNG', optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    rgb = (ramp((img - env[:, None] - lo) / (hi - lo))[::-1] * 255).astype(np.uint8)         # top row = highest frequency
    main = png(np.asarray(Image.fromarray(rgb).resize((X1 - X0, Y1 - Y0), Image.LANCZOS)))     # at its drawn size: 220 kB, not 450
    lane = png((ramp(feat['chroma'])[::-1] * 255).astype(np.uint8))                          # top row = B, bottom = C
    o = head(W, H, 'Twenty-four seconds of a record, through the converter',
             'Everything in Its Right Place, 2:05 to 2:29, left channel of the ripper’s 48 kHz output.')
    o.append(f'<image x="{X0}" y="{Y0}" width="{X1-X0}" height="{Y1-Y0}" preserveAspectRatio="none" xlink:href="data:image/png;base64,{main}"/>')
    o.append(f'<image x="{X0}" y="{CY0}" width="{X1-X0}" height="{CY1-CY0}" preserveAspectRatio="none" style="image-rendering:pixelated" xlink:href="data:image/png;base64,{lane}"/>')
    py = lambda fr: Y1 - (np.log10(fr) - np.log10(FMIN)) / (np.log10(FMAX) - np.log10(FMIN)) * (Y1 - Y0)
    px = lambda t: X0 + t / seconds * (X1 - X0)
    for fr, lab in ((50,'50'),(100,'100'),(200,'200'),(500,'500'),(1e3,'1k'),(2e3,'2k'),(5e3,'5k'),(10e3,'10k'),(20e3,'20k')):
        y = py(fr); o.append(f'<line x1="{X0-4}" y1="{y:.1f}" x2="{X0}" y2="{y:.1f}" stroke="{MUTED}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{X0-8}" y="{y+4:.1f}" text-anchor="end">{lab}</text>')
    o.append(f'<text class="a" x="{X0-8}" y="{Y0-8}" text-anchor="end">Hz</text>')
    # the bands, with their notes; the hits, ticked above the plot
    for b in feat['bands']:
        y = py(b['hz'])
        o.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X1}" y2="{y:.1f}" stroke="rgba(255,255,255,0.35)" stroke-width="0.8" stroke-dasharray="3 4"/>')
        o.append(f'<text x="{X1+6}" y="{y+4:.1f}" style="font:12px system-ui,sans-serif" fill="{INK_2}">{esc(b["note"])} · {b["hz"]:.0f} Hz</text>')
    for t in feat['onsets']:
        o.append(f'<line x1="{px(t):.1f}" y1="{Y0-10}" x2="{px(t):.1f}" y2="{Y0-2}" stroke="rgba(255,255,255,0.45)" stroke-width="1"/>')
    o.append(f'<text x="{X1}" y="{Y0-14}" text-anchor="end" style="font:12px system-ui,sans-serif" fill="{MUTED}">{len(feat["onsets"])} hits detected</text>')
    # what is what, written on the picture
    for fr, lab in ((11000, 'highs · percussion ticks and the record’s surface noise'), (3200, 'beats · vertical stripes'),
                    (380, 'chord tones · horizontal bands'), (38, 'bass')):
        o.append(f'<text x="{X0+8}" y="{py(fr)+4:.1f}" style="font:600 11.5px system-ui,sans-serif;paint-order:stroke;stroke:{SURFACE};stroke-width:4px;stroke-linejoin:round" fill="{INK}">{esc(lab)}</text>')
    # lanes
    o.append(f'<text x="{X0}" y="{CY0-5}" style="font:11px system-ui,sans-serif" fill="{MUTED}">loudest note</text>')
    for k, name in enumerate(NOTE_NAMES[::-1]):
        o.append(f'<text class="a" x="{X0-8}" y="{CY0 + (k + 0.5) * (CY1-CY0) / 12 + 3.5:.1f}" text-anchor="end" style="font-size:10.5px">{esc(name)}</text>')
    o.append(f'<text x="{X0}" y="{HY0-5}" style="font:11px system-ui,sans-serif" fill="{MUTED}">beat activity</text>')
    fl = feat['flux']; pts = ' '.join(f'{px(c * sg["hop"] / FS):.1f},{HY1 - v * (HY1-HY0):.1f}' for c, v in enumerate(fl))
    o.append(f'<polygon points="{px(0):.1f},{HY1} {pts} {px(len(fl) * sg["hop"] / FS):.1f},{HY1}" fill="{LEFT}" opacity="0.85"/>')
    for t in range(0, int(seconds) + 1, 4):
        o.append(f'<line x1="{px(t):.1f}" y1="{HY1}" x2="{px(t):.1f}" y2="{HY1+4}" stroke="{MUTED}" stroke-width="1"/>')
        o.append(f'<text class="a" x="{px(t):.1f}" y="{HY1+18}" text-anchor="middle">{t} s</text>')
    # colour key, above the plot on the left
    kx, ky, kw = X0 + 34, 55, 160
    o.append('<defs><linearGradient id="k" x1="0" x2="1" y1="0" y2="0">' +
             ''.join(f'<stop offset="{p*100:.0f}%" stop-color="rgb({int(c[0]*255)},{int(c[1]*255)},{int(c[2]*255)})"/>'
                     for p, c in zip(np.linspace(0, 1, 9), ramp(np.linspace(0, 1, 9)))) + '</linearGradient></defs>')
    o.append(f'<rect x="{kx}" y="{ky}" width="{kw}" height="8" fill="url(#k)" rx="2"/>')
    o.append(f'<text class="a" x="{kx-6}" y="{ky+8}" text-anchor="end">{lo:+.0f}</text>')
    o.append(f'<text class="a" x="{kx+kw+6}" y="{ky+8}">{hi:+.0f} dB against the usual level at that pitch</text>')
    o.append('</svg>'); out.write_text('\n'.join(o) + '\n'); return out

# ------------------------------------------------- interactive export
def interactive_export(sg, feat, outdir, seconds):
    """What the page's canvas draws from: the spectrogram's absolute dB values as a grayscale PNG, the
    loudest-note lane as another, and a JSON with the axes, the reference level per row, the features."""
    from PIL import Image
    img, env, lo, hi = sg['img'], sg['env'], sg['lo'], sg['hi']
    g = np.clip((img - lo) / (hi - lo), 0, 1)[::-1]            # top row = highest frequency, like the figure
    Image.fromarray((g * 255).astype(np.uint8), mode='L').save(outdir / 'music-spectrogram-data.png', optimize=True)
    Image.fromarray((feat['chroma'][::-1] * 255).astype(np.uint8), mode='L').save(outdir / 'music-spectrogram-chroma.png', optimize=True)
    meta = dict(seconds=round(seconds, 3), fmin=FMIN, fmax=FMAX, cols=int(sg['cols']), rows=int(img.shape[0]),
                db_lo=lo, db_hi=hi, rel_lo=sg['rel_lo'], rel_hi=sg['rel_hi'], hop_s=sg['hop'] / FS,
                windows=[[n, f] for n, f in WINDOWS[:-1]] + [[WINDOWS[-1][0], FMAX]],
                env=[round(float(v), 1) for v in env[::-1]],                       # per PNG row, top first
                bands=feat['bands'], onsets=feat['onsets'], moments=feat['moments'],
                flux=[round(float(v), 2) for v in feat['flux']], chroma_rows=NOTE_NAMES[::-1])
    (outdir / 'music-spectrogram-data.json').write_text(json.dumps(meta, ensure_ascii=False) + '\n')
    print('  bands: ' + ', '.join(f"{b['hz']:.0f} Hz {b['note']}" for b in feat['bands']))
    print(f"  onsets: {len(feat['onsets'])}; moments: {feat['moments']}")
    return [outdir / n for n in ('music-spectrogram-data.png', 'music-spectrogram-chroma.png', 'music-spectrogram-data.json')]

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
    sg = spectrogram_data(music); feat = features(music, sg)
    outs = [spectrogram_figure(sg, feat, outdir / 'music-spectrogram.svg', seconds),
            floor_figure(music, idle, outdir / 'music-vs-floor.svg'), *interactive_export(sg, feat, outdir, seconds)]
    for p in outs:
        print(f'  wrote {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}  ({p.stat().st_size/1024:.0f} kB)')

if __name__ == '__main__':
    main()
