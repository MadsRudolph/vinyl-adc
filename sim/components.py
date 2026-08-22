"""Step 7: turn the coefficients into real component values, then check that
the SNAPPED values still work.

Snapping to E96 is not a formality.  Every coefficient is an R*C product, so
rounding six resistors is a perturbation of the loop filter, and the only
honest way to know it is harmless is to re-run the modulator on the values that
will actually be soldered down.

Scales:
  V_D  DAC half-swing.  The 74HC gate swings 0/5 V and an equal offset resistor
       to a -2.5 V reference recentres it, so the net feedback is +/-2.5 V.
  S1..S3  the voltage each integrator's state maps to.  Chosen so the op-amps
       run well inside their swing at normal levels but SATURATE on a big
       overload -- that saturation is the only thing that stops a vinyl click
       latching the loop up permanently (see verify.py).
  S_u  input voltage at 1.0 FS.
"""

import numpy as np
from modulator import Modulator, sweep_amplitude

FS = 1.536e6
OSR = 32
DELAY = 200e-9 * FS

A1, A2, A3 = 0.250, 0.320, 0.610
G = 0.0300
K0 = -0.225

V_D = 2.5                  # DAC half-swing, volts
S1, S2, S3 = 2.04, 1.79, 1.47
S_U = 3.486                # full scale with the level trim at max;
                           # Rin = 20k5 falls straight out of this
C_INT = 220e-12            # C0G ceramic, all three integrators
R_S = 22.0e3               # V3 -> comparator summing resistor

E96 = np.array([100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130,
                133, 137, 140, 143, 147, 150, 154, 158, 162, 165, 169, 174,
                178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232,
                237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
                316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412,
                422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549,
                562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732,
                750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976])


def e96(x):
    """Snap to the nearest E96 value (the shop stocks the full series)."""
    d = int(np.floor(np.log10(x))) - 2
    cand = E96 * 10.0 ** d
    cand = np.concatenate([cand, cand * 10])
    return float(cand[np.argmin(np.abs(cand - x))])


def fmt(r):
    if r >= 1e6:
        return f"{r/1e6:.4g}M"
    if r >= 1e3:
        return f"{r/1e3:.4g}k"
    return f"{r:.4g}R"


def synthesise():
    v = {}
    # --- integrator 1 -----------------------------------------------------
    v["Rd1"] = e96(V_D / (FS * S1 * A1 * C_INT))
    v["Rin"] = e96(v["Rd1"] * S_U / V_D)
    # --- integrator 2 -----------------------------------------------------
    v["R2"] = e96(S1 / (FS * S2 * A2 * C_INT))
    v["Rd2"] = e96(V_D / (FS * S2 * A2 * C_INT))
    v["Rg"] = e96(S3 / (FS * S2 * A2 * G * C_INT))
    # --- integrator 3 -----------------------------------------------------
    v["R3"] = e96(S2 / (FS * S3 * A3 * C_INT))
    v["Rd3"] = e96(V_D / (FS * S3 * A3 * C_INT))
    # --- quantiser summing node ------------------------------------------
    v["Rs"] = e96(R_S)
    v["Rk0"] = e96(V_D * R_S / (abs(K0) * S3))
    return v


def coeffs_from(v):
    """Invert the synthesis: what coefficients do these real parts give?"""
    a1 = V_D / (FS * S1 * v["Rd1"] * C_INT)
    a2 = S1 / (FS * S2 * v["R2"] * C_INT)
    a2v = V_D / (FS * S2 * v["Rd2"] * C_INT)
    a3 = S2 / (FS * S3 * v["R3"] * C_INT)
    a3v = V_D / (FS * S3 * v["Rd3"] * C_INT)
    g = S3 / (FS * S2 * v["Rg"] * C_INT) / a2
    k0 = -V_D * v["Rs"] / (v["Rk0"] * S3)
    # k1..k3 are the ratio of each DAC weight to that stage's forward gain
    return dict(a=[a1, a2, a3], k=[1.0, a2v / a2, a3v / a3], g=g, k0=k0,
                su=V_D * v["Rin"] / v["Rd1"])


def check(c, label, n=1 << 16):
    m = Modulator(c["a"], k=c["k"], g=c["g"], k0=c["k0"],
                  gbw=3e6 / FS, delay=DELAY)
    print(f"  {label}")
    for A, s, ok, pk in sweep_amplitude(m, FS, OSR,
                                        [0.2, 0.3, 0.4, 0.5, 0.6, 0.7], n=n):
        if not ok or np.max(pk) > 12:
            print(f"     {20*np.log10(A):6.1f} dBFS   OVERLOAD")
        else:
            volts = " ".join(f"{p*s_:4.2f}V" for p, s_ in
                             zip(pk[::2] if len(pk) == 6 else pk, (S1, S2, S3)))
            print(f"     {20*np.log10(A):6.1f} dBFS   {s:6.1f} dB   {volts}")


def noise_budget(v):
    """Input-referred noise, 20 Hz - 20 kHz, against a 2 Vrms signal."""
    k, T, BW = 1.380649e-23, 300.0, 20000.0
    en = 18e-9          # TL07x voltage noise
    # integrator 1 sums the source, the DAC and nothing else
    rpar = 1.0 / (1.0 / v["Rin"] + 1.0 / v["Rd1"])
    e_amp = en * (v["Rin"] / rpar)
    e_rin = np.sqrt(4 * k * T * v["Rin"])
    e_rd1 = np.sqrt(4 * k * T * v["Rd1"]) * (v["Rin"] / v["Rd1"])
    tot = np.sqrt(e_amp ** 2 + e_rin ** 2 + e_rd1 ** 2) * np.sqrt(BW)
    print(f"  op-amp  {e_amp*1e9:5.1f} nV/rtHz -> {e_amp*np.sqrt(BW)*1e6:5.2f} uVrms")
    print(f"  Rin     {e_rin*1e9:5.1f} nV/rtHz -> {e_rin*np.sqrt(BW)*1e6:5.2f} uVrms")
    print(f"  Rd1     {e_rd1*1e9:5.1f} nV/rtHz -> {e_rd1*np.sqrt(BW)*1e6:5.2f} uVrms")
    print(f"  total input-referred: {tot*1e6:.2f} uVrms")
    print(f"  -> thermal-noise SNR vs 2 Vrms: {20*np.log10(2.0/tot):.0f} dB "
          f"(quantisation noise dominates at ~70 dB)")


def jitter(sigma_j, label):
    """Crude NRZ-DAC clock-jitter floor.

    Each DAC edge lands sigma_j early or late, so it delivers the wrong charge
    for that long.  Relative charge error per edge is sigma_j/T; those errors
    are white, so oversampling buys back a factor of OSR.
    """
    T = 1.0 / FS
    err = sigma_j / T
    snr = -10 * np.log10(err ** 2 * 2.0 / OSR)
    print(f"  {label:28s} sigma_j {sigma_j*1e12:8.0f} ps -> jitter floor "
          f"{snr:5.0f} dB")


if __name__ == "__main__":
    v = synthesise()
    print("=" * 70)
    print(f"Component values   (C1=C2=C3={C_INT*1e12:.0f} pF C0G, fs={FS/1e6:.3f} MHz)")
    print("=" * 70)
    ideal = {
        "Rd1": V_D / (FS * S1 * A1 * C_INT),
        "Rin": V_D / (FS * S1 * A1 * C_INT) * S_U / V_D,
        "R2": S1 / (FS * S2 * A2 * C_INT),
        "Rd2": V_D / (FS * S2 * A2 * C_INT),
        "Rg": S3 / (FS * S2 * A2 * G * C_INT),
        "R3": S2 / (FS * S3 * A3 * C_INT),
        "Rd3": V_D / (FS * S3 * A3 * C_INT),
        "Rs": R_S,
        "Rk0": V_D * R_S / (abs(K0) * S3),
    }
    names = {"Rin": "input -> int1", "Rd1": "DAC -> int1",
             "R2": "int1 -> int2", "Rd2": "DAC -> int2",
             "Rg": "int3 -> int2 (resonator)", "R3": "int2 -> int3",
             "Rd3": "DAC -> int3", "Rs": "int3 -> comparator",
             "Rk0": "DAC -> comparator (ELD comp)"}
    for kk in ("Rin", "Rd1", "R2", "Rd2", "Rg", "R3", "Rd3", "Rs", "Rk0"):
        err = 100 * (v[kk] - ideal[kk]) / ideal[kk]
        print(f"  {kk:5s} {fmt(v[kk]):>8s}   (ideal {fmt(ideal[kk]):>8s}, "
              f"{err:+5.2f}%)   {names[kk]}")

    c = synthesise() and coeffs_from(v)
    print()
    print(f"  realised: a=[{c['a'][0]:.4f}, {c['a'][1]:.4f}, {c['a'][2]:.4f}]  "
          f"k=[{c['k'][0]:.3f}, {c['k'][1]:.3f}, {c['k'][2]:.3f}]")
    print(f"            g={c['g']:.5f}  k0={c['k0']:.4f}")
    print(f"  target:   a=[{A1:.4f}, {A2:.4f}, {A3:.4f}]  k=[1,1,1]  "
          f"g={G:.5f}  k0={K0:.4f}")
    print(f"  full-scale input {c['su']:.2f} Vpk "
          f"({c['su']/np.sqrt(2):.2f} Vrms); 2 Vrms sits at "
          f"{20*np.log10(2*np.sqrt(2)/c['su']):.1f} dBFS")

    print()
    print("=" * 70)
    print("Re-simulated with the SNAPPED values (TL074, 200 ns loop delay)")
    print("=" * 70)
    check(c, "E96 values as they will be soldered:")

    print()
    print("=" * 70)
    print("Noise budget")
    print("=" * 70)
    noise_budget(v)
    print()
    jitter(20e-12, "crystal oscillator can")
    jitter(1e-9, "Pi GPCLK0 (fractional div)")
