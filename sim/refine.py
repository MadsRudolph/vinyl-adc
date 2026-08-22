"""Step 5: local refinement of the final coefficient set.

Everything here is evaluated with the non-idealities switched ON (LF356 GBW and
the LM311's 200 ns in the loop), because those are the conditions the board
will actually run in.  Optimising against ideal op-amps and then bolting the
delay on afterwards is how you end up with a design that only works in theory.
"""

import numpy as np
from modulator import Modulator, sweep_amplitude

FCLK = 1.536e6
OSR = 32
GBW = 5.0e6
TCOMP = 200e-9
DELAY = TCOMP * FCLK          # 0.31 of a clock period
STATE_MAX = 12.0


def score(a, g, k0, n=1 << 15):
    """(snr at 0.5 FS, max bounded amplitude). -inf if it cannot reach 0.5."""
    m = Modulator(list(a), g=g, k0=k0, gbw=GBW / FCLK, delay=DELAY)
    rows = sweep_amplitude(m, FCLK, OSR, [0.5, 0.7], n=n)
    snr5, amax = float("-inf"), 0.0
    for A, s, ok, pk in rows:
        if ok and np.max(pk) < STATE_MAX:
            amax = max(amax, A)
            if A == 0.5:
                snr5 = s
    return snr5, amax


def refine(a0, g0, k00):
    best = (score(a0, g0, k00), tuple(a0), g0, k00)
    print(f"  start  a={a0} g={g0:.4f} k0={k00:.2f} -> "
          f"{best[0][0]:.1f} dB, stable to {best[0][1]:.2f} FS")

    steps = [0.05, 0.02, 0.01]
    for step in steps:
        improved = True
        while improved:
            improved = False
            (bs, ba, bg, bk) = best
            for i in range(3):
                for d in (+step, -step):
                    a = list(ba)
                    a[i] = round(a[i] + d, 4)
                    if a[i] <= 0.02:
                        continue
                    s = score(a, bg, bk)
                    if s[0] > bs[0] and s[1] >= 0.7:
                        best = (s, tuple(a), bg, bk)
                        improved = True
            (bs, ba, bg, bk) = best
            for d in (+step / 5, -step / 5):
                g = round(bg + d, 5)
                if g < 0:
                    continue
                s = score(ba, g, bk)
                if s[0] > bs[0] and s[1] >= 0.7:
                    best = (s, ba, g, bk)
                    improved = True
            (bs, ba, bg, bk) = best
            for d in (+step / 2, -step / 2):
                k0 = round(bk + d, 4)
                s = score(ba, bg, k0)
                if s[0] > bs[0] and s[1] >= 0.7:
                    best = (s, ba, bg, k0)
                    improved = True
    return best


if __name__ == "__main__":
    print("=" * 74)
    print(f"Refining at fclk {FCLK/1e6:.3f} MHz, OSR {OSR}, GBW {GBW/1e6:.0f} MHz, "
          f"loop delay {DELAY*100:.0f}% Ts")
    print("=" * 74)
    (s, amax), a, g, k0 = refine([0.25, 0.30, 0.65], 0.0300, -0.20)
    print()
    print(f"  FINAL  a=[{a[0]:.3f}, {a[1]:.3f}, {a[2]:.3f}]  g={g:.5f}  k0={k0:.3f}")
    print(f"         {s:.1f} dB at -6 dBFS, stable to {amax:.2f} FS")

    print()
    print("  level sweep (long run):")
    m = Modulator(list(a), g=g, k0=k0, gbw=GBW / FCLK, delay=DELAY)
    for A, sn, ok, pk in sweep_amplitude(
            m, FCLK, OSR, [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], n=1 << 17):
        if not ok or np.max(pk) >= STATE_MAX:
            print(f"     {20*np.log10(A):6.1f} dBFS   OVERLOAD")
        else:
            st = " ".join(f"{p:5.2f}" for p in pk)
            print(f"     {20*np.log10(A):6.1f} dBFS   {sn:6.1f} dB   states {st}")
