"""Continuous-time delta-sigma modulator simulator for the discrete vinyl ADC.

Models the actual circuit rather than a DT prototype, because the parts we are
stuck with (5 MHz op-amps, a 200 ns comparator) make the non-idealities the
whole story.

Topology: CIFB (cascade of integrators, feedback). Each integrator is an
inverting op-amp integrator; the 1-bit DAC is an NRZ voltage driven by the
retiming flip-flop, injected into each integrator's virtual ground through one
resistor. That makes every feedback path a single resistor -- the cheapest
thing that can possibly work on a hand-built board.

    X1' = a1*(u - k1*v)
    X2' = a2*(X1 - k2*v)
    X3' = a3*(X2 - k3*v)
    v   = sign(X3) sampled at fs and held (the D flip-flop)

Time is normalised to the clock period, so ai = 1/(Ri*Ci*fs) is dimensionless
and the coefficients transfer straight onto real RC values.

Optional non-idealities:
  * finite op-amp GBW  -> each integrator gets an extra pole at GBW
  * excess loop delay  -> comparator + flip-flop delay, as a fraction of Ts
  * integrator clipping -> op-amp output saturation at the supply rails
"""

import numpy as np


# --------------------------------------------------------------------------
# small matrix exponential (scipy is not installed)
# --------------------------------------------------------------------------

def expm(A, terms=18):
    """exp(A) by scaling-and-squaring with a Taylor series."""
    A = np.asarray(A, dtype=float)
    norm = np.abs(A).sum(axis=1).max()
    s = max(0, int(np.ceil(np.log2(norm))) + 1) if norm > 0 else 0
    As = A / (2.0 ** s)
    E = np.eye(A.shape[0])
    T = np.eye(A.shape[0])
    for k in range(1, terms + 1):
        T = T @ As / k
        E = E + T
    for _ in range(s):
        E = E @ E
    return E


def _discretise(A, B, h):
    """Exact zero-order-hold discretisation of X' = A X + B w over step h.

    Uses the block-matrix trick: expm([[A, B], [0, 0]] * h) has Ad in the top
    left and Bd in the top right.
    """
    n, m = B.shape
    M = np.zeros((n + m, n + m))
    M[:n, :n] = A
    M[:n, n:] = B
    E = expm(M * h)
    return E[:n, :n], E[:n, n:]


# --------------------------------------------------------------------------
# the modulator
# --------------------------------------------------------------------------

class Modulator:
    """CIFB continuous-time modulator, order = len(a).

    With ``g`` non-zero the last two integrators form a resonator (local
    feedback X[n-1] -> input of integrator n-2), which lifts the NTF zeros off
    DC and spreads them across the audio band.  On the board that is one extra
    resistor, and it is worth about 10 dB.
    """

    def __init__(self, a, k=None, g=0.0, k0=0.0, gbw=None, delay=0.0, clip=None):
        self.a = np.asarray(a, dtype=float)
        self.n = len(self.a)
        self.k = np.ones(self.n) if k is None else np.asarray(k, dtype=float)
        self.g = float(g)
        # k0: excess-loop-delay compensation -- a direct path from the DAC to
        # the quantiser input, bypassing every integrator.  On the board it is
        # one resistor into a passive summer at the comparator input.
        self.k0 = float(k0)
        self.gbw = gbw          # op-amp GBW / fs, per stage (None = ideal)
        self.delay = delay      # excess loop delay, fraction of Ts
        self.clip = clip        # integrator output limit, in units of Vref

    # -- state-space of the loop filter -----------------------------------
    def _ss(self):
        n = self.n
        if self.gbw is None:
            A = np.zeros((n, n))
            for i in range(1, n):
                A[i, i - 1] = self.a[i]
            if self.g and n >= 3:
                A[n - 2, n - 1] = -self.a[n - 2] * self.g
            B = np.zeros((n, 2))
            B[0, 0] = self.a[0]
            for i in range(n):
                B[i, 1] = -self.a[i] * self.k[i]
            return A, B

        # Finite GBW: an op-amp integrator with unity-gain bandwidth wt behaves
        # as a second-order system.  Model it as the ideal integrator followed
        # by a one-pole lag at wt -- the dominant effect, and the one that eats
        # phase margin in the loop.
        g = np.atleast_1d(np.asarray(self.gbw, dtype=float))
        if g.size == 1:
            g = np.repeat(g, n)
        wt = 2.0 * np.pi * g          # rad per clock period
        N = 2 * n                      # [int_1, lag_1, int_2, lag_2, ...]
        A = np.zeros((N, N))
        B = np.zeros((N, 2))
        for i in range(n):
            xi, li = 2 * i, 2 * i + 1
            # integrator i is driven by the *lag output* of stage i-1
            if i > 0:
                A[xi, 2 * (i - 1) + 1] = self.a[i]
            else:
                B[xi, 0] = self.a[0]
            B[xi, 1] = -self.a[i] * self.k[i]
            # lag: l' = wt*(x - l)
            A[li, xi] = wt[i]
            A[li, li] = -wt[i]
        if self.g and n >= 3:
            A[2 * (n - 2), 2 * (n - 1) + 1] = -self.a[n - 2] * self.g
        return A, B

    # -- linearised analysis (fast; no time stepping) ----------------------
    def ntf(self, w):
        """NTF magnitude on the unit circle at normalised frequencies w (rad).

        The quantiser decides on x[n] and its output only reaches the state at
        x[n+1], so the loop already carries one sample of delay:
            L(z) = C (zI - Ad)^-1 Bd_v ,  NTF = 1 / (1 - L)

        The minus sign is not a typo: Bd_v is built from B[:,1] = -a_i*k_i, so
        the negative feedback is already inside L.  Writing 1/(1+L) here gives
        an NTF whose peak is below unity, which Bode says is impossible -- that
        is the cheap check that this sign is right.
        """
        A, B = self._ss()
        Ad, Bd = _discretise(A, B, 1.0)
        N = A.shape[0]
        oi = self._out_index()
        z = np.exp(1j * np.asarray(w, dtype=float))

        # batched (zI - Ad) x = Bd_v, one solve for every frequency at once
        M = np.broadcast_to(-Ad.astype(complex), (z.size, N, N)).copy()
        idx = np.arange(N)
        M[:, idx, idx] += z[:, None]
        rhs = np.broadcast_to(Bd[:, 1].astype(complex), (z.size, N))
        X = np.linalg.solve(M, rhs[..., None])[..., 0]
        L = X[:, oi] + self.k0
        return 1.0 / (1.0 - L)

    def poles(self):
        """Closed-loop poles with the quantiser linearised to unity gain.

        B[:,1] already carries the sign of the feedback, so the closed loop is
        simply Ad + Bd_v C.  Any |pole| >= 1 means the *linear* loop diverges --
        no amount of Lee-rule hand-waving rescues it, and every such candidate
        blew up in the time-domain run.
        """
        A, B = self._ss()
        Ad, Bd = _discretise(A, B, 1.0)
        N = A.shape[0]
        C = np.zeros((1, N))
        C[0, self._out_index()] = 1.0
        gain = 1.0 / (1.0 - self.k0) if self.k0 else 1.0
        return np.linalg.eigvals(Ad + gain * (Bd[:, 1:2] @ C))

    def predict(self, osr, npts=1024, nband=256):
        """(peak_snr_dB at 0 dBFS, ||NTF||inf) from the linear model.

        Returns snr = -inf when the linearised loop is unstable, so callers can
        screen on the SNR alone.  Quantiser noise is modelled as white with
        variance dlt^2/12 = 1/3 for the +/-1 levels, spread over 0..pi.
        """
        if np.abs(self.poles()).max() >= 0.999:
            return float("-inf"), float("inf")

        wb = np.pi / osr
        w_band = np.linspace(1e-9, wb, nband)
        w_all = np.linspace(1e-9, np.pi, npts)
        H = np.abs(self.ntf(np.concatenate([w_band, w_all])))
        Hb, Ha = H[:nband], H[nband:]

        hinf = Ha.max()
        pn = np.trapezoid(Hb ** 2, w_band) / np.pi * (1.0 / 3.0)
        snr_fs = 10.0 * np.log10(0.5 / pn) if pn > 0 else float("inf")
        return snr_fs, hinf

    def _out_index(self):
        return (self.n - 1) if self.gbw is None else (2 * self.n - 1)

    # -- run ---------------------------------------------------------------
    def run(self, u):
        """Feed input array u (one sample per clock, |u|<1). Return (v, states)."""
        A, B = self._ss()
        N = A.shape[0]
        oidx = self._out_index()

        if self.delay > 0.0:
            h1 = self.delay
            h2 = 1.0 - self.delay
            Ad1, Bd1 = _discretise(A, B, h1)
            Ad2, Bd2 = _discretise(A, B, h2)
        else:
            Ad, Bd = _discretise(A, B, 1.0)

        x = np.zeros(N)
        v = np.zeros(len(u))
        vprev = 1.0
        peak = np.zeros(N)
        unstable = False

        for i, ui in enumerate(u):
            if self.delay > 0.0:
                # The flip-flop samples on the clock edge, but the comparator
                # and the D-FF take time to propagate, so the DAC still shows
                # the PREVIOUS decision for the first `delay` of the period.
                # Deciding after that advance instead would let the quantiser
                # see a fresher state than the real circuit ever does.
                y = x[oidx] + self.k0 * vprev
                vi = 1.0 if y > 0 else -1.0
                x = Ad1 @ x + Bd1 @ np.array([ui, vprev])
                x = Ad2 @ x + Bd2 @ np.array([ui, vi])
            else:
                # no excess delay: the DAC value the quantiser sees through the
                # k0 path is the decision being made right now, so solve the
                # one-line fixed point instead of using a stale value
                y0 = x[oidx]
                vi = 1.0 if (y0 + self.k0) > 0 else -1.0
                if self.k0 and (y0 + self.k0 > 0) != (y0 - self.k0 > 0):
                    vi = 1.0 if y0 > 0 else -1.0
                w = np.array([ui, vi])
                x = Ad @ x + Bd @ w

            if self.clip is not None:
                lo, hi = ((-self.clip, self.clip)
                          if np.isscalar(self.clip) else self.clip)
                np.clip(x, lo, hi, out=x)

            peak = np.maximum(peak, np.abs(x))
            if not np.all(np.isfinite(x)) or np.abs(x).max() > 1e6:
                unstable = True
                v[i:] = 0.0
                break

            v[i] = vi
            vprev = vi

        return v, dict(peak=peak, unstable=unstable)


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------

def snr(v, fs, f_sig, band=(20.0, 20000.0), skip=4096):
    """In-band SNR of a 1-bit stream, in dB. Hann-windowed periodogram."""
    x = v[skip:]
    n = len(x)
    w = np.hanning(n)
    X = np.fft.rfft(x * w)
    p = np.abs(X) ** 2
    f = np.fft.rfftfreq(n, 1.0 / fs)

    # signal power: the three bins around f_sig (Hann main lobe)
    kseg = int(round(f_sig * n / fs))
    lo, hi = max(0, kseg - 2), kseg + 3
    ps = p[lo:hi].sum()

    inband = (f >= band[0]) & (f <= band[1])
    pn = p[inband].sum() - p[lo:hi][inband[lo:hi]].sum()
    if pn <= 0:
        return float("inf")
    return 10.0 * np.log10(ps / pn)


def sweep_amplitude(mod, fs, osr, amps, n=1 << 16, f_sig=997.0):
    """Peak-SNR curve. Returns list of (amplitude, snr_dB, stable, peak_states)."""
    # snap f_sig to an FFT bin so leakage does not dominate
    nn = n - 4096
    kseg = max(1, int(round(f_sig * nn / fs)))
    f_sig = kseg * fs / nn

    t = np.arange(n) / fs
    out = []
    for A in amps:
        u = A * np.sin(2 * np.pi * f_sig * t)
        v, info = mod.run(u)
        if info["unstable"]:
            out.append((A, float("nan"), False, info["peak"]))
            continue
        s = snr(v, fs, f_sig, band=(20.0, fs / (2 * osr)))
        out.append((A, s, True, info["peak"]))
    return out
