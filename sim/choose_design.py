"""Step 3: choose the final coefficients.

The linear model ranks candidates cheaply but lies about stability, so here it
is used only to shortlist.  The non-linear time-domain run then decides, with
two hard requirements:

  * must still be stable at 0.75 FS -- vinyl clicks are large transients and a
    1-bit loop that latches up stays latched until something resets it
  * SNR is scored at 0.5 FS (-6 dBFS), which is the level Mads already targets
    when recording
"""

import itertools
import numpy as np
from modulator import Modulator, sweep_amplitude

FS = 1.536e6
OSR = 32
SCORE_AT = 0.5
MUST_SURVIVE = 0.75


def shortlist(order, osr, hinf_max, ntop=40):
    a1s = np.arange(0.10, 0.90, 0.025)
    a2s = np.arange(0.20, 1.60, 0.05)
    a3s = np.arange(0.20, 1.60, 0.05)
    gs = [0.0] + list(np.arange(0.001, 0.030, 0.001) * (32.0 / osr) ** 2)

    rough = []
    for a1, a2, a3 in itertools.product(a1s, a2s, a3s):
        a = [a1, a2, a3][:order]
        s, h = Modulator(a).predict(osr, npts=384, nband=128)
        if np.isfinite(s) and 1.0 <= h <= hinf_max:
            rough.append((s, tuple(a)))
    rough.sort(reverse=True)

    out = []
    for _, a in rough[:120]:
        for g in (gs if order >= 3 else [0.0]):
            s, h = Modulator(list(a), g=g).predict(osr, npts=384, nband=128)
            if np.isfinite(s) and 1.0 <= h <= hinf_max:
                out.append((s, h, a, g))
    out.sort(reverse=True)

    seen, uniq = set(), []
    for s, h, a, g in out:
        key = (a, round(g, 4))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((s, h, a, g))
        if len(uniq) == ntop:
            break
    return uniq


def evaluate(a, g, order_note=""):
    m = Modulator(list(a), g=g)
    rows = sweep_amplitude(m, FS, OSR, [SCORE_AT, MUST_SURVIVE], n=1 << 15)
    (_, s_score, ok_score, pk), (_, _, ok_surv, pk2) = rows
    if not (ok_score and ok_surv):
        return None
    return s_score, max(pk2)


if __name__ == "__main__":
    print("=" * 74)
    print("Stability / SNR trade-off, order 3, OSR 32, fclk 1.536 MHz")
    print(f"score at {SCORE_AT:.2f} FS, must stay stable at {MUST_SURVIVE:.2f} FS")
    print("=" * 74)

    overall = []
    for hcap in (1.30, 1.40, 1.50, 1.60):
        cands = shortlist(3, OSR, hcap, ntop=25)
        best = None
        for s_lin, h, a, g in cands:
            r = evaluate(a, g)
            if r is None:
                continue
            s_sim, pk = r
            if best is None or s_sim > best[0]:
                best = (s_sim, pk, s_lin, h, a, g)
        if best is None:
            print(f"  Hinf <= {hcap:.2f}: no candidate survived {MUST_SURVIVE} FS")
            continue
        s_sim, pk, s_lin, h, a, g = best
        astr = ",".join(f"{x:.3f}" for x in a)
        print(f"  Hinf <= {hcap:.2f}:  {s_sim:5.1f} dB @ {SCORE_AT} FS   "
              f"(linear {s_lin:.1f})  Hinf {h:.2f}  peak state {pk:4.2f}")
        print(f"                a=[{astr}]  g={g:.4f}")
        overall.append(best)

    print()
    print("=" * 74)
    print("Order 2 at the same clock, for comparison")
    print("=" * 74)
    best2 = None
    for s_lin, h, a, g in shortlist(2, OSR, 1.60, ntop=25):
        r = evaluate(a, g)
        if r is None:
            continue
        if best2 is None or r[0] > best2[0]:
            best2 = (r[0], r[1], s_lin, h, a, g)
    if best2:
        s_sim, pk, s_lin, h, a, g = best2
        astr = ",".join(f"{x:.3f}" for x in a[:2])
        print(f"  best order 2: {s_sim:5.1f} dB @ {SCORE_AT} FS   Hinf {h:.2f}"
              f"   a=[{astr}]")

    if overall:
        pick = max(overall, key=lambda r: r[0])
        print()
        print("=" * 74)
        s_sim, pk, s_lin, h, a, g = pick
        print(f"PICK: a=[{','.join(f'{x:.3f}' for x in a)}]  g={g:.4f}")
        print(f"      {s_sim:.1f} dB at {SCORE_AT} FS, Hinf {h:.2f}, "
              f"peak integrator swing {pk:.2f} x Vref at {MUST_SURVIVE} FS")
        print("=" * 74)
