#!/usr/bin/env python3
"""Cut level-matched, time-aligned A/B excerpts for the listening bench.

    python3 media/ab/make_ab.py --ref before.flac --start 125 --seconds 24 \
        --add "after.flac=After the repair — stereo" \
        --add "original.flac=Digital release" \
        --out ab/

The reference excerpt is cut as-is. Every other source is aligned to it: a coarse
search over the whole file at 4.8 kHz finds where the excerpt is, then two fine
searches at full rate - one at the start of the window, one at the end - give the
exact offset AND the speed ratio (a record played twice never runs at the same
speed, and this converter clocks itself 190 ppm off nominal). The source is
resampled by that ratio, cut, matched to the reference's RMS and written as
16-bit 48 kHz WAV next to a sources.json the bench page reads.

Vinyl and digital masters are different masters. Aligning them makes switching
seamless; it does not make their spectra equal, and the bench says so.

Needs only ffmpeg and NumPy. The audio this produces is a personal comparison
copy of a commercial recording: it is git-ignored here and must not be published.
"""
import argparse, json, subprocess, sys, wave
from pathlib import Path
import numpy as np

FS = 48000

def decode(path):
    """Stereo float32 at 48 kHz, shape (2, n)."""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '2', '-ar', str(FS), '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype='<f4').reshape(-1, 2).T.copy()

def xcorr_peak(a, b):
    """Lag of b relative to a maximising |correlation| (a and b zero-mean, b shorter than a). FFT-based."""
    n = len(a) + len(b) - 1; nfft = 1 << (n - 1).bit_length()
    A = np.fft.rfft(a, nfft); B = np.fft.rfft(b, nfft)
    c = np.fft.irfft(A * np.conj(B), nfft)[:len(a)]
    k = int(np.argmax(np.abs(c)))
    return k, float(c[k] / (np.linalg.norm(a[k:k+len(b)]) * np.linalg.norm(b) + 1e-12))

def align(ref_win, other, start_ref, seconds):
    """Return (offset_seconds, speed_ratio, quality) placing `other` onto the reference window."""
    L_ref = ref_win[0] - ref_win[0].mean(); L_oth = other[0] - other[0].mean()
    # coarse: whole file at 4.8 kHz
    D = 10
    k, q = xcorr_peak(L_oth[::D], L_ref[::D])
    coarse = k * D
    # fine: 3 s pieces at the start and the end of the window, searched ±0.4 s around the coarse guess
    def fine(at):
        piece = L_ref[at:at + 3 * FS]; lo = max(0, coarse + at - int(0.4 * FS)); hi = min(len(L_oth), coarse + at + len(piece) + int(0.4 * FS))
        kk, qq = xcorr_peak(L_oth[lo:hi], piece); return lo + kk - at, qq
    s0, q0 = fine(0); s1, q1 = fine(len(L_ref) - 3 * FS)
    speed = 1.0 + (s1 - s0) / (len(L_ref) - 3 * FS)       # other runs `speed` times as fast as the reference
    return s0 / FS, speed, min(q0, q1)

def resample(x, ratio):
    """Linear resample of (2, n) by `ratio` (>1 = other is faster, so stretch it out)."""
    n = x.shape[1]; m = int(round(n * ratio)); t = np.linspace(0, n - 1, m)
    return np.vstack([np.interp(t, np.arange(n), x[c]) for c in range(2)])

def write_wav(path, x):
    y = np.clip(x, -1, 1); pcm = (y.T * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS); w.writeframes(pcm.tobytes())

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--ref', required=True); p.add_argument('--ref-label', default='Before the repair — mono fallback')
    p.add_argument('--ref-note', default='')
    p.add_argument('--start', type=float, required=True); p.add_argument('--seconds', type=float, default=24)
    p.add_argument('--add', action='append', default=[], metavar='FILE=LABEL[=NOTE]')
    p.add_argument('--out', type=Path, default=Path('ab'))
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)

    ref = decode(a.ref); i0 = int(a.start * FS); n = int(a.seconds * FS)
    ref_win = ref[:, i0:i0 + n]; ref_rms = np.sqrt((ref_win ** 2).mean())
    write_wav(a.out / 'before.wav', ref_win)
    sources = [dict(label=a.ref_label, note=a.ref_note, file='before.wav', gain_db=0.0)]
    print(f"reference: {a.ref}  window {a.start:.1f}s +{a.seconds:.0f}s  rms {20*np.log10(ref_rms):.1f} dBFS")

    for k, spec in enumerate(a.add, 1):
        parts = spec.split('=', 2); path = parts[0]; label = parts[1] if len(parts) > 1 else Path(path).stem; note = parts[2] if len(parts) > 2 else ''
        oth = decode(path)
        off, speed, q = align(ref_win, oth, a.start, a.seconds)
        # stretch the other source so the window lands sample for sample on the reference
        j0 = int(round(off * FS)); span = int(round(n * speed)) + FS
        piece = oth[:, max(0, j0):max(0, j0) + span]
        piece = resample(piece, 1 / speed)[:, :n]
        if piece.shape[1] < n: piece = np.pad(piece, ((0, 0), (0, n - piece.shape[1])))
        gain = ref_rms / (np.sqrt((piece ** 2).mean()) + 1e-12)
        piece = piece * gain
        fn = f'source{k}.wav'; write_wav(a.out / fn, piece)
        corr = float(np.corrcoef(piece[0], ref_win[0])[0, 1])
        rel = off - a.start          # where the excerpt sits in this file, relative to where it sits in the reference
        sources.append(dict(label=label, note=note, file=fn, gain_db=round(20 * np.log10(gain), 2),
                            offset_s=round(rel, 3), speed_ppm=round((speed - 1) * 1e6), align_quality=round(q, 3)))
        print(f"  {label}: offset {rel:+.3f} s, speed {(speed-1)*1e6:+.0f} ppm, align quality {q:.3f}, "
              f"gain {20*np.log10(gain):+.2f} dB, L-channel correlation with reference after alignment {corr:+.3f}")
    (a.out / 'sources.json').write_text(json.dumps(dict(duration=a.seconds, sources=sources), indent=2) + '\n')
    print(f"wrote {a.out/'sources.json'} with {len(sources)} source(s)")

if __name__ == '__main__':
    main()
