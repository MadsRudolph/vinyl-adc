"""Step 2: pick the loop coefficients.

Two-stage search.  Stage 1 sweeps the integrator gains with the resonator off;
stage 2 tunes the resonator on the best survivors.  Both stages score with the
linearised NTF, which is cheap; only the finalists get the full non-linear
time-domain run.

Stability screen is Lee's rule for a 1-bit quantiser, ||NTF||inf <~ 1.5.  It is
a rule of thumb, not a theorem, which is exactly why the finalists are then
simulated for real.
"""

import itertools
import numpy as np
from modulator import Modulator, sweep_amplitude

HINF_MAX = 2.00   # Lee's 1.5 proved far too tight here; the time-domain
                  # run below is the real arbiter of stability
HINF_MIN = 1.0   # Bode: a stable monic NTF must exceed 1 somewhere. A screen
                 # result below this means the loop is not actually stable.


def stage1(order, osr, a1s, a2s, a3s):
    out = []
    for a1, a2, a3 in itertools.product(a1s, a2s, a3s):
        a = [a1, a2, a3][:order]
        try:
            s, h = Modulator(a).predict(osr)
        except np.linalg.LinAlgError:
            continue
        if np.isfinite(s) and HINF_MIN <= h <= HINF_MAX:
            out.append((s, h, tuple(a), 0.0))
    out.sort(reverse=True)
    return out


def stage2(order, osr, seeds, gs):
    if order < 3:
        return seeds
    out = list(seeds)
    for _, _, a, _ in seeds:
        for g in gs:
            try:
                s, h = Modulator(list(a), g=g).predict(osr)
            except np.linalg.LinAlgError:
                continue
            if np.isfinite(s) and HINF_MIN <= h <= HINF_MAX:
                out.append((s, h, a, g))
    out.sort(reverse=True)
    return out


def search(order, osr, ntop=150):
    a1s = np.arange(0.10, 0.90, 0.05)
    a2s = np.arange(0.20, 1.80, 0.10)
    a3s = np.arange(0.20, 1.80, 0.10)
    gs = np.arange(0.001, 0.040, 0.0015) * (32.0 / osr) ** 2
    s1 = stage1(order, osr, a1s, a2s, a3s)
    return stage2(order, osr, s1[:ntop], gs)


def show(tag, res, n=5):
    if not res:
        print(f"  {tag}: nothing met the stability screen")
        return
    print(f"  {tag}")
    for s, h, a, g in res[:n]:
        astr = ",".join(f"{x:.2f}" for x in a)
        print(f"     {s:6.1f} dB @0 dBFS   Hinf {h:4.2f}   a=[{astr}]  g={g:.4f}")


if __name__ == "__main__":
    print("=" * 74)
    print("A. Order 2 vs 3 at OSR 32  (fclk 1.536 MHz -- what LF356/LM311 allow)")
    print("=" * 74)
    r2 = search(2, 32)
    r3 = search(3, 32)
    show("order 2", r2)
    show("order 3", r3)

    print()
    print("=" * 74)
    print("B. What a faster clock would buy (order 3)")
    print("=" * 74)
    for osr, fclk in ((32, 1.536e6), (48, 2.304e6), (64, 3.072e6)):
        r = search(3, osr, ntop=60)
        if r:
            s, h, a, g = r[0]
            astr = ",".join(f"{x:.2f}" for x in a)
            print(f"  OSR {osr:3d} (fclk {fclk/1e6:5.3f} MHz): {s:6.1f} dB   "
                  f"Hinf {h:4.2f}  a=[{astr}] g={g:.4f}")

    print()
    print("=" * 74)
    print("C. Time-domain confirmation of the order-3 / OSR-32 finalists")
    print("=" * 74)
    seen = set()
    finalists = []
    for s, h, a, g in r3:
        key = (a, round(g, 4))
        if key in seen:
            continue
        seen.add(key)
        finalists.append((s, h, a, g))
        if len(finalists) == 4:
            break

    for s_lin, h, a, g in finalists:
        astr = ",".join(f"{x:.2f}" for x in a)
        print(f"\n  a=[{astr}] g={g:.4f}   (linear {s_lin:.1f} dB, Hinf {h:.2f})")
        m = Modulator(list(a), g=g)
        for A, s, ok, peak in sweep_amplitude(m, 1.536e6, 32,
                                              [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                                              n=1 << 16):
            if not ok:
                print(f"     {A:4.2f} FS   UNSTABLE")
            else:
                st = " ".join(f"{p:5.2f}" for p in peak)
                print(f"     {A:4.2f} FS   {s:6.1f} dB   peak states {st}")
