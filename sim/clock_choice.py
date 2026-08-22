"""Step 4: choose the clock rate against the real parts.

A faster clock is worth ~20 dB (OSR 32 -> 64), so it is worth knowing exactly
what breaks first.  Two shop-imposed limits scale with fclk:

  LF356   GBW 5 MHz  -> gbw/fs = 5e6/fclk, an extra pole inside each integrator
  LM311   ~200 ns    -> excess loop delay = 200ns/T, the comparator + D-FF path

Both are modelled here.  "Stable" means the integrator states stay bounded --
their absolute size does not matter, because dynamic-range scaling can move any
bounded state into the op-amp's swing without touching the NTF.
"""

import itertools
import numpy as np
from modulator import Modulator, sweep_amplitude

GBW = 5.0e6        # LF356
TCOMP = 200e-9     # LM311 response time
STATE_MAX = 12.0   # bounded-operation bound, pre-scaling
HINF_MAX = 1.50


def best_coeffs(osr, hinf_max=HINF_MAX, ntop=30):
    a1s = np.arange(0.10, 0.70, 0.025)
    a2s = np.arange(0.15, 1.20, 0.05)
    a3s = np.arange(0.20, 1.40, 0.05)
    gs = [0.0] + list(np.arange(0.002, 0.040, 0.002) * (32.0 / osr) ** 2)

    rough = []
    for a1, a2, a3 in itertools.product(a1s, a2s, a3s):
        s, h = Modulator([a1, a2, a3]).predict(osr, npts=384, nband=128)
        if np.isfinite(s) and 1.0 <= h <= hinf_max:
            rough.append((s, (a1, a2, a3)))
    rough.sort(reverse=True)

    out = []
    for _, a in rough[:120]:
        for g in gs:
            s, h = Modulator(list(a), g=g).predict(osr, npts=384, nband=128)
            if np.isfinite(s) and 1.0 <= h <= hinf_max:
                out.append((s, h, a, g))
    out.sort(reverse=True)
    seen, uniq = set(), []
    for s, h, a, g in out:
        key = (a, round(g, 4))
        if key not in seen:
            seen.add(key)
            uniq.append((s, h, a, g))
        if len(uniq) == ntop:
            break
    return uniq


def characterise(a, g, fclk, osr, gbw=None, delay=0.0, amps=None):
    """Return (snr at 0.5FS, snr at 0.25FS, max stable amplitude)."""
    amps = amps or [0.125, 0.25, 0.5, 0.6, 0.7, 0.8]
    gbw_n = None if gbw is None else gbw / fclk
    m = Modulator(list(a), g=g, gbw=gbw_n, delay=delay)
    rows = sweep_amplitude(m, fclk, osr, amps, n=1 << 15)
    snr_at = {}
    amax = 0.0
    for A, s, ok, peak in rows:
        bounded = ok and np.max(peak) < STATE_MAX
        if bounded:
            amax = max(amax, A)
            snr_at[A] = s
    return snr_at, amax


if __name__ == "__main__":
    for osr, fclk in ((32, 1.536e6), (48, 2.304e6), (64, 3.072e6)):
        print("=" * 74)
        print(f"OSR {osr}   fclk {fclk/1e6:.3f} MHz   "
              f"GBW/fs = {GBW/fclk:.2f}   comparator delay = "
              f"{TCOMP*fclk*100:.0f}% of a clock period")
        print("=" * 74)

        cands = best_coeffs(osr)
        chosen = None
        for s_lin, h, a, g in cands:
            snr_ideal, amax = characterise(a, g, fclk, osr)
            if amax < 0.7 or 0.5 not in snr_ideal:
                continue
            chosen = (a, g, h, s_lin, snr_ideal, amax)
            break

        if chosen is None:
            print("  no candidate stayed bounded to 0.7 FS\n")
            continue

        a, g, h, s_lin, snr_ideal, amax = chosen
        astr = ",".join(f"{x:.3f}" for x in a)
        print(f"  coefficients a=[{astr}] g={g:.4f}  (Hinf {h:.2f})")
        print(f"  ideal op-amps:      {snr_ideal[0.5]:5.1f} dB @0.5FS   "
              f"stable to {amax:.2f} FS")

        snr_g, amax_g = characterise(a, g, fclk, osr, gbw=GBW)
        got = f"{snr_g[0.5]:5.1f} dB" if 0.5 in snr_g else "UNSTABLE"
        print(f"  + LF356 5 MHz GBW:  {got} @0.5FS   stable to {amax_g:.2f} FS")

        d = min(0.9, TCOMP * fclk)
        snr_d, amax_d = characterise(a, g, fclk, osr, gbw=GBW, delay=d)
        got = f"{snr_d[0.5]:5.1f} dB" if 0.5 in snr_d else "UNSTABLE"
        print(f"  + LM311 delay:      {got} @0.5FS   stable to {amax_d:.2f} FS")
        print()
