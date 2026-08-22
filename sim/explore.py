"""Step 1 of the design: how much order do we actually need at OSR 32?

fs is pinned near 1.5 MHz by the parts the DTU shop stocks (LF356 = 5 MHz GBW,
LM311 = 200 ns), so OSR = fs/48k is around 32.  The question this answers is
whether a 2nd-order loop clears the 65-75 dB target at that OSR, or whether we
have to pay for a third integrator.
"""

import numpy as np
from modulator import Modulator, sweep_amplitude

FS = 1.536e6
OSR = 32
AMPS = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def report(name, mod, n=1 << 16):
    rows = sweep_amplitude(mod, FS, OSR, AMPS, n=n)
    best_s, best_a = -999.0, None
    print(f"\n{name}")
    print(f"  {'ampl':>6} {'SNR dB':>8} {'ENOB':>6}   peak integrator states")
    for A, s, ok, peak in rows:
        if not ok:
            print(f"  {A:6.2f} {'UNSTABLE':>8}")
            continue
        st = " ".join(f"{p:5.2f}" for p in peak)
        print(f"  {A:6.2f} {s:8.1f} {(s - 1.76) / 6.02:6.2f}   {st}")
        if s > best_s:
            best_s, best_a = s, A
    print(f"  -> peak {best_s:.1f} dB at amplitude {best_a}")
    return best_s


if __name__ == "__main__":
    print("=" * 70)
    print(f"fs = {FS/1e6:.3f} MHz   OSR = {OSR}   output = {FS/OSR/1e3:.1f} kHz")
    print("ideal integrators, no excess loop delay")
    print("=" * 70)

    # --- 2nd order, a small sweep of coefficient pairs -------------------
    print("\n### ORDER 2 ###")
    for a in ([0.5, 0.5], [0.4, 0.6], [0.3, 0.8], [0.25, 1.0], [0.2, 0.5]):
        report(f"a = {a}", Modulator(a))

    # --- 3rd order -------------------------------------------------------
    print("\n### ORDER 3 ###")
    for a in ([0.4, 0.4, 0.4], [0.3, 0.5, 0.5], [0.2, 0.5, 0.8],
              [0.25, 0.5, 0.5], [0.15, 0.4, 0.7]):
        report(f"a = {a}", Modulator(a))
