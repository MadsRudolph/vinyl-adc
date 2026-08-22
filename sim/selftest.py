"""Validate the simulator against a textbook discrete-time modulator.

If a plain DT 2nd-order modulator does not land near the classic
    SNR = 6.02 + 1.76 - 10*log10(pi^4/5) + 50*log10(OSR)
then the measurement is wrong, not the design.
"""

import numpy as np
from modulator import snr

FS = 1.536e6
OSR = 32
NB = FS / (2 * OSR)


def theory(order, osr):
    L = order
    return (6.02 + 1.76
            - 10 * np.log10(np.pi ** (2 * L) / (2 * L + 1))
            + 10 * (2 * L + 1) * np.log10(osr))


def dt_modulator(u, order=2, a=None):
    """Classic DT CIFB with delaying integrators, coefficients a."""
    if a is None:
        a = [1.0] * order
    x = np.zeros(order)
    v = np.zeros(len(u))
    vi = 1.0
    for i, ui in enumerate(u):
        vi = 1.0 if x[-1] > 0 else -1.0
        v[i] = vi
        nx = x.copy()
        nx[0] = x[0] + a[0] * (ui - vi)
        for j in range(1, order):
            nx[j] = x[j] + a[j] * (x[j - 1] - vi)
        x = nx
    return v


if __name__ == "__main__":
    n = 1 << 17
    skip = 4096
    nn = n - skip
    k = int(round(997.0 * nn / FS))
    f_sig = k * FS / nn
    t = np.arange(n) / FS

    print(f"fs={FS/1e6:.3f} MHz  OSR={OSR}  band=0..{NB/1e3:.0f} kHz  "
          f"f_sig={f_sig:.1f} Hz  N={n}")
    print()
    for order, a in ((1, [1.0]), (2, [0.5, 0.5]), (2, [1.0, 1.0]),
                     (3, [0.2, 0.5, 0.5])):
        best = -999
        for A in (0.1, 0.3, 0.5, 0.7, 0.8):
            u = A * np.sin(2 * np.pi * f_sig * t)
            v = dt_modulator(u, order, a)
            if not np.all(np.isfinite(v)):
                continue
            s = snr(v, FS, f_sig, band=(20.0, NB), skip=skip)
            best = max(best, s)
        print(f"  DT order {order} a={a}: measured peak {best:6.1f} dB "
              f"| theory {theory(order, OSR):6.1f} dB")
