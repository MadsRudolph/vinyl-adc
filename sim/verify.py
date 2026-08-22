"""Step 6: does the design survive real parts?

Two questions the coefficient search cannot answer:

  1. Is a TL074 (3 MHz) good enough for all three integrators, or does the
     first one need an LF356 (5 MHz)?
  2. Component tolerance.  Every coefficient is an R*C product, so a 1%
     resistor and a 10% film cap put +/-10% on each ai.  A design that only
     works at nominal is not a design.
"""

import numpy as np
from modulator import Modulator, sweep_amplitude

FCLK = 1.536e6
OSR = 32
DELAY = 200e-9 * FCLK
STATE_MAX = 12.0

A = [0.250, 0.320, 0.610]
G = 0.0300
K0 = -0.225


def run(a, g, k0, gbw, delay=DELAY, n=1 << 15, amps=(0.5, 0.7)):
    m = Modulator(list(a), g=g, k0=k0,
                  gbw=None if gbw is None else gbw / FCLK, delay=delay)
    snr5, amax = float("nan"), 0.0
    for Amp, s, ok, pk in sweep_amplitude(m, FCLK, OSR, list(amps), n=n):
        if ok and np.max(pk) < STATE_MAX:
            amax = max(amax, Amp)
            if Amp == 0.5:
                snr5 = s
    return snr5, amax


if __name__ == "__main__":
    print("=" * 70)
    print("1. Op-amp GBW  (final coefficients, 200 ns loop delay)")
    print("=" * 70)
    for gbw, label in ((None, "ideal"), (10e6, "10 MHz"), (5e6, "LF356  5 MHz"),
                       (3e6, "TL07x  3 MHz"), (2e6, "2 MHz"), (1e6, "1 MHz")):
        s, amax = run(A, G, K0, gbw)
        print(f"   {label:14s}  {s:5.1f} dB @-6 dBFS   overloads above "
              f"{20*np.log10(amax):.1f} dBFS")

    print()
    print("=" * 70)
    print("2. Component tolerance Monte Carlo, TL074 (3 MHz)")
    print("   ai from a 1% resistor and a 10% film cap -> ~10% each")
    print("=" * 70)
    rng = np.random.default_rng(20260822)
    for tol, ctol in ((0.05, "5% caps"), (0.10, "10% caps")):
        snrs, fails = [], 0
        N = 120
        for _ in range(N):
            a = [A[i] * (1 + rng.uniform(-tol, tol)) for i in range(3)]
            g = G * (1 + rng.uniform(-tol, tol))
            k0 = K0 * (1 + rng.uniform(-0.02, 0.02))   # resistor ratio only
            s, amax = run(a, g, k0, 3e6, n=1 << 14)
            if not np.isfinite(s) or amax < 0.7:
                fails += 1
            if np.isfinite(s):
                snrs.append(s)
        snrs = np.array(snrs)
        print(f"   {ctol}:  median {np.median(snrs):5.1f} dB   "
              f"worst {snrs.min():5.1f} dB   "
              f"5th pct {np.percentile(snrs,5):5.1f} dB")
        print(f"             {fails}/{N} lost overload margin below -3 dBFS")

    print()
    print("=" * 70)
    print("3. Overload recovery -- does it come back after a vinyl click?")
    print("=" * 70)
    n = 1 << 15
    t = np.arange(n) / FCLK
    f = 997.0
    u = 0.45 * np.sin(2 * np.pi * f * t)
    u[n // 4:n // 4 + 60] += 3.0            # a big transient, way past FS
    m = Modulator(A, g=G, k0=K0, gbw=3e6 / FCLK, delay=DELAY)
    v, info = m.run(np.clip(u, -4, 4))
    tail = v[n // 2:]
    print(f"   peak states during/after the click: "
          f"{np.array2string(info['peak'], precision=2)}")
    print(f"   output still toggling afterwards: "
          f"{'yes' if 0.02 < np.mean(tail > 0) < 0.98 else 'NO - LATCHED'}")
    print(f"   mean of last quarter: {np.mean(v[-n//4:]):+.3f} "
          f"(should be near 0 for a small signal)")
