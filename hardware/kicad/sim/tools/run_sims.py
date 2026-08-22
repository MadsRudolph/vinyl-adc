#!/usr/bin/env python
r"""Export each testbench through KiCad, run it, and check the DESIGN's numbers.

    C:\Users\Mads2\miniconda3\python.exe tools\run_sims.py [a b c ...]

Verification harness only.  The sheets themselves are ordinary KiCad
schematics that run in Eeschema's own simulator; this exports the same
netlist KiCad would hand ngspice and asserts what docs/design-notes.md says
the circuit does, so a broken testbench is caught here rather than by eye.

Every bound below comes from the design record, not from what the models
happen to do -- tools/test_models.py is where the models answer to their
datasheets.  A model and a check that shared an assumption would agree with
each other and both be wrong, which is exactly how an inverted comparator
model once passed its own test on another board.
"""
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PySpice.Spice.NgSpice.Shared import NgSpiceShared

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
SIM = Path(__file__).resolve().parent.parent
NG = NgSpiceShared.new_instance(verbose=False)
RESULTS = []

# from docs/design-notes.md section 3, the state scales in volts per unit
S1, S2, S3 = 2.04, 1.79, 1.47
V_D = 2.5                      # DAC half-swing
F_MCLK = 1.536e6


# ----------------------------------------------------------------- plumbing
def netlist(bench):
    out = SIM / "build" / f"{bench}.cir"
    out.parent.mkdir(exist_ok=True)
    r = subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format",
                        "spice", "-o", str(out),
                        str(SIM / f"{bench}.kicad_sch")],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{bench}: netlist export failed\n{r.stdout}{r.stderr}")
    return out.read_text(encoding="utf-8")


def simulate(deck):
    try:
        NG.remove_circuit()
    except Exception:  # noqa: BLE001 - nothing loaded on the first call
        pass
    NG.load_circuit(deck)
    try:
        NG.run()
    except Exception:  # noqa: BLE001
        # ngspice returns a non-zero status whenever it fell back on dynamic
        # gmin stepping, which it does for any deck whose operating point
        # starts with an amplifier against its clamp -- and then runs the
        # analysis perfectly.  The plot is the real test.
        pass
    plot = NG.plot(None, NG.last_plot)
    w = {k.lower(): np.asarray(v.to_waveform()) for k, v in plot.items()}
    if len(w.get("time", ())) < 2:
        raise RuntimeError("analysis produced no data")
    return w


def check(name, got, lo, hi, unit=""):
    ok = got is not None and np.isfinite(got) and lo <= got <= hi
    RESULTS.append((ok, name))
    g = "None" if got is None else f"{got:.5g}"
    print(f"    {'PASS' if ok else 'FAIL'}  {name:50s} {g:>11}{unit}"
          f"  want {lo:g}..{hi:g}{unit}")


def report(name, value, unit=""):
    """A measurement worth printing that is not a pass/fail claim."""
    print(f"    ....  {name:50s} {value:>11.5g}{unit}")


def edges(t, v, level=2.5, rising=True):
    out = []
    for i in range(1, len(v)):
        a, b = v[i - 1], v[i]
        if (rising and a < level <= b) or (not rising and a > level >= b):
            f = (level - a) / (b - a) if b != a else 0.0
            out.append(t[i - 1] + f * (t[i] - t[i - 1]))
    return np.array(out)


def freq(t, v, level=2.5):
    e = edges(t, v, level)
    return 1.0 / np.mean(np.diff(e)) if len(e) > 2 else None


def duty(t, v, level=2.5):
    up, dn = edges(t, v, level, True), edges(t, v, level, False)
    if len(up) < 3 or len(dn) < 3:
        return None
    period = float(np.mean(np.diff(up)))
    dn = dn[dn > up[0]]
    n = min(len(up), len(dn))
    return float(np.mean(dn[:n] - up[:n])) / period * 100.0


def detrended_pp(t, v):
    """Peak-to-peak with any linear drift removed."""
    res = v - np.polyval(np.polyfit(t, v, 1), t)
    return float(res.max() - res.min())


def window(t, lo, hi):
    return (t >= lo) & (t <= hi)


def ramp_rates(t, v, drive, hold, t0, t1, frac=(0.55, 0.95)):
    """Settled integrator ramp rate between DAC edges, in V/s, up and down.

    A 3 MHz op-amp takes about three time constants -- 150 ns -- to reach
    full slope after each DAC edge, so the MEDIAN instantaneous slope over a
    651 ns half period reads 4 % low and the triangle's peak-to-peak reads
    6 % low.  Neither is a loss of charge: the amplifier delivers all of it,
    just late.  So fit the settled part of each ramp, and report the rounding
    separately rather than letting it masquerade as a wrong coefficient.
    """
    ups = [e for e in edges(t, drive) if t0 < e < t1]
    dns = [e for e in edges(t, drive, rising=False) if t0 < e < t1]
    out = []
    for group in (ups, dns):
        slopes = []
        for e in group:
            sel = window(t, e + frac[0] * hold, e + frac[1] * hold)
            if sel.sum() > 3:
                slopes.append(np.polyfit(t[sel], v[sel], 1)[0])
        out.append(float(np.median(slopes)) if slopes else float("nan"))
    return out[0], out[1]


# ------------------------------------------------------------------ benches
def bench_a():
    """The charge pump: -5 V rail, ripple, and that it inverts at all."""
    w = simulate(netlist("sim_a_pump"))
    t, v, node = w["time"], w["-5v"], w["pumpnode"]

    # THE polarity check.  Both Schottkys were drawn backwards, which makes
    # this a voltage doubler putting +3.4 V on every op-amp's V- pin; every
    # other gate in the toolkit passed that version, because a diode wired
    # the wrong way round is still a connected diode.
    check("pump node swings below the negative rail (V)",
          float(node.min()), -5.0, -3.0, " V")
    check("pump node never rises far above ground (V)",
          float(node.max()), -0.1, 1.0, " V")

    final = float(v[-1])
    report("settled rail", final, " V")
    report("load current", abs(final) / 130.0 * 1e3, " mA")
    # the design's requirement, not its estimate: the TL074s must clear a
    # 1.94 V peak swing, and the part needs about 1.5 V of headroom
    check("rail deep enough for a 1.94 V peak swing (V)", final, -4.6, -3.44,
          " V")
    # docs/design-notes.md 6: ripple below 1 uV after 4R75 + 220u
    T = 32.0 / 6.144e6
    sel = t > t[-1] - 2 * T
    check("ripple after the RC filter (uV)",
          detrended_pp(t[sel], v[sel]) * 1e6, 0, 1.0, " uV")
    # and it has to be up before the analog section is asked to work
    half = float(v[np.searchsorted(t, 40e-3)])
    check("rail within 5 % of final by 40 ms (V)", half, final * 1.05,
          final * 0.95, " V")


def bench_b():
    """The reference: 2.5 V, and ratiometric to the rail moment by moment."""
    w = simulate(netlist("sim_b_reference"))
    t = w["time"]
    sel = t > 0.2e-3
    p, n, rail = w["vref_p"][sel], w["vref_n"][sel], w["+5v"][sel]
    check("VREF_P mean (V)", float(p.mean()), 2.495, 2.505, " V")
    check("VREF_N mean (V)", float(n.mean()), -2.505, -2.495, " V")
    # the point of the whole block: rail noise must arrive as a common-mode
    # gain modulation, which is only true if VREF tracks the rail exactly
    check("worst |VREF_P - rail/2| (uV)",
          float(np.max(np.abs(p - rail / 2))) * 1e6, 0, 1000, " uV")
    check("worst |VREF_N + VREF_P| (uV)",
          float(np.max(np.abs(n + p))) * 1e6, 0, 1000, " uV")
    # 100 mV of hum on a 5 V rail is a 2 % modulation; -98 dB of it survives
    ripple = float(p.max() - p.min())
    report("VREF_P follows the rail's 100 mV hum by", ripple * 1e3, " mVpp")


def bench_c():
    """The divider: four exact binary clocks, and how much skew they cost."""
    w = simulate(netlist("sim_c_clock"))
    t = w["time"]
    sel = t > 5e-6
    tt = t[sel]
    for node, want in (("bclk", 3.072e6), ("mclk", 1.536e6),
                       ("pump", 192e3), ("lrclk", 48e3)):
        f = freq(tt, w[node][sel])
        check(f"{node.upper()} frequency (kHz)", f / 1e3 if f else None,
              want * 0.995 / 1e3, want * 1.005 / 1e3, " kHz")
    for node in ("bclk", "mclk", "pump"):
        check(f"{node.upper()} duty (%)", duty(tt, w[node][sel]), 49, 51, " %")
    check("BCLK swings the rail (Vpp)",
          float(w["bclk"][sel].max() - w["bclk"][sel].min()), 4.9, 5.05, " Vpp")
    # the HCT buffer's whole job: a 3.3 V source still clocks a 5 V chain
    check("a 3.3 V source still drives CLK6M to the rail (Vpp)",
          float(w["clk6m"][sel].max() - w["clk6m"][sel].min()), 4.9, 5.05,
          " Vpp")
    # ripple skew: every extra stage delays its output, and that comes
    # straight off the 163 ns of I2S setup margin (docs/design-notes.md 4b)
    eb = edges(tt, w["bclk"][sel], rising=False)
    el = edges(tt, w["lrclk"][sel], rising=False)
    skew = min(abs(x - eb[np.argmin(np.abs(eb - x))]) for x in el[1:4])
    report("BCLK to LRCLK ripple skew", skew * 1e9, " ns")
    check("ripple skew leaves the setup margin intact (ns)", skew * 1e9,
          0, 100, " ns")


def bench_d():
    """One integrator: its coefficient, and where the TL074 really stops."""
    w = simulate(netlist("sim_d_integrator"))
    t, out, sumn = w["time"], w["int1"], w["sum1"]

    # With the input at zero the DAC alone drives it, so the ramp RATE is
    # a1 x S1 per clock period: 0.247 x 2.04 V = 0.503 V.
    # Measure the slope, not the triangle's peak-to-peak: a 3 MHz op-amp
    # rounds the corners off, which costs about 6 % of the height while the
    # ramp itself -- the charge the DAC actually delivers -- is untouched.
    T = 1.0 / F_MCLK
    r1, r2 = ramp_rates(t, out, w["dacn_l"], T, 10e-6, 36e-6)
    rate = (abs(r1) + abs(r2)) / 2
    ideal = V_D / (14.7e3 * 220e-12)
    report("settled DAC-driven ramp rate", rate / 1e3, " kV/s")
    report("  as a fraction of 2.5 V / (14k7 x 220p)", rate / ideal * 100, " %")
    report("triangle peak-to-peak (corners rounded by the 3 MHz TL074)",
           detrended_pp(t[window(t, 10e-6, 36e-6)],
                        out[window(t, 10e-6, 36e-6)]) * 1e3, " mVpp")
    # The TL074's 3 MHz costs about 3.5 % of the ramp -- an ideal amplifier
    # gives 100.0 % and a 30 MHz one 99.7 %, so this is the part, not the
    # measurement.  It is a systematic 3.5 % on every ai, well inside the
    # +/-10 % Monte Carlo of docs/design-notes.md 7, and sim/verify.py's GBW
    # sweep already shows the loop does not care: the Python model carries
    # the same lag.
    check("a1 from the ramp rate (dimensionless)", rate * T / S1, 0.230, 0.255)

    # The input path: a full-scale step ramps at 1/(Rin x C1).  Measure over
    # a whole number of DAC periods or the toggling DAC leaves a residue in
    # the answer -- over 1 us it reads 10 % low.
    s0 = 40.6e-6
    s1 = s0 + 2 * T
    i0, i1 = np.searchsorted(t, s0), np.searchsorted(t, s1)
    slope = (out[i1] - out[i0]) / (t[i1] - t[i0])
    report("  as a fraction of 3.486 V / (20k5 x 220p)",
           abs(slope) / (3.486 / (20.5e3 * 220e-12)) * 100, " %")
    check("full-scale input slope (kV/s)", slope / 1e3, -800, -710, " kV/s")

    # THE load-bearing number: with no clamp parts anywhere, the op-amp's own
    # saturation is what stops a vinyl click latching the modulator
    sat = float(out[window(t, 50e-6, 68e-6)].min())
    report("negative saturation on +/-5 V rails", sat, " V")
    report("  as a multiple of the integrator-1 state scale", abs(sat) / S1)
    check("saturation lands where the design needs it (V)", sat, -4.0, -2.0,
          " V")
    # the TL074's input common-mode floor is V- + 4 V, so -1 V here.  A
    # virtual earth is only virtual while the amplifier is still in control.
    check("summing node stays above the TL074 CM floor (V)",
          float(sumn[t > 1e-6].min()), -1.0, 1.0, " V")


def bench_e():
    """The quantiser: single-supply biasing, and the ELD threshold shift."""
    w = simulate(netlist("sim_e_quantiser"))
    t, sumc, cmp_, v3, dacp = (w["time"], w["sumc"], w["cmp_l"], w["v3"],
                               w["dacp_l"])
    sel = t > 20e-6
    check("summing node sits on VREF_P (V)", float(sumc[sel].mean()),
          2.45, 2.55, " V")
    # the LM311's single-supply input range is 0.5 V to V+ - 1.5 V
    check("summing node stays inside the LM311 CM range, low (V)",
          float(sumc[sel].min()), 0.5, 2.5, " V")
    check("summing node stays inside the LM311 CM range, high (V)",
          float(sumc[sel].max()), 2.5, 3.5, " V")
    check("comparator output swings the rail (Vpp)",
          float(cmp_[sel].max() - cmp_[sel].min()), 4.6, 5.05, " Vpp")

    # Rk0 shifts the threshold by +/-0.335 V of V3 as the DAC switches, which
    # is |k0| x S3.  Read the V3 value at each comparator edge and split the
    # edges by which DAC level was standing at the time.
    up = edges(t, cmp_)
    up = up[up > 20e-6]
    lo, hi = [], []
    for te in up:
        i = np.searchsorted(t, te)
        (hi if dacp[i] > 2.5 else lo).append(np.interp(te, t, v3))
    thr_lo, thr_hi = float(np.median(lo)), float(np.median(hi))
    report("threshold with the DAC low", thr_lo, " V")
    report("threshold with the DAC high", thr_hi, " V")
    check("threshold is centred with the DAC at its mean (mV)",
          (thr_lo + thr_hi) / 2 * 1e3, -30, 30, " mV")
    k0 = (thr_lo - thr_hi) / 2 / S3
    check("|k0| from the threshold shift", abs(k0), 0.210, 0.245)

    # the LM311's 200 ns is what Rk0 exists to compensate; check it is there
    # the + input is VREF_P and the - input is the summing node, so the
    # output goes HIGH as the summing node falls THROUGH 2.5 V
    cross = edges(t, sumc, level=2.5, rising=False)
    cross = cross[cross > 20e-6]
    lags = []
    for tc in cross:
        nxt = up[(up > tc) & (up < tc + 2e-6)]
        if len(nxt):
            lags.append(nxt[0] - tc)
    check("comparator propagation delay (ns)",
          float(np.median(lags)) * 1e9 if lags else None, 150, 280, " ns")


def bench_f():
    """The 1-bit DAC: is the feedback really +/-2.5 V about the reference?"""
    w = simulate(netlist("sim_f_dac"))
    t = w["time"]
    out = {"integrator 1 (14k7)": (w["int1"], 14.7e3),
           "integrator 2 (13k0)": (w["int2"], 13.0e3)}
    for label, (v, rd) in out.items():
        ideal = V_D / (rd * 220e-12)
        r1, r2 = ramp_rates(t, v, w["dacn_l"] if "1" in label else w["dacp_l"],
                            1.0 / F_MCLK, 5e-6, 35e-6)
        a1_, a2_ = abs(r1), abs(r2)
        report(f"{label} ramp one way", a1_ / 1e3, " kV/s")
        report(f"{label} ramp the other", a2_ / 1e3, " kV/s")
        # 3.5 % of the shortfall is the TL074's 3 MHz, measured on bench D
        check(f"{label}: ramp vs 2.5 V / (Rd x C) (%)",
              (a1_ + a2_) / 2 / ideal * 100, 95.0, 101.0, " %")
        # The two DAC levels must be symmetric about the reference.  What
        # asymmetry there is comes from the 74HC04's own 50 ohm of output
        # resistance, which the ideal model in ../../../sim does not have:
        # a gain error and a DC offset in the feedback, never distortion.
        asym = (a1_ - a2_) / (a1_ + a2_) * 2
        report(f"{label} level asymmetry", asym * 100, " %")
        check(f"{label}: DAC levels symmetric to better than 2 %",
              abs(asym) * 100, 0, 2.0, " %")


def bench_g():
    """The Pi interface: does 32 L + 32 R really land in one I2S frame?"""
    w = simulate(netlist("sim_g_interface"))
    t = w["time"]
    sel = t > 10e-6
    tt = t[sel]
    check("PI_BCLK swings 3.3 V (Vpp)",
          float(w["pi_bclk"][sel].max() - w["pi_bclk"][sel].min()), 3.2, 3.4,
          " Vpp")
    check("PI_LRCLK swings 3.3 V (Vpp)",
          float(w["pi_lrclk"][sel].max() - w["pi_lrclk"][sel].min()), 3.2,
          3.4, " Vpp")
    fb = freq(tt, w["pi_bclk"][sel], level=1.65)
    fl = freq(tt, w["pi_lrclk"][sel], level=1.65)
    check("PI_BCLK frequency (kHz)", fb / 1e3 if fb else None, 3056, 3088,
          " kHz")
    check("BCLK cycles per LRCLK frame", fb / fl if fb and fl else None,
          63.5, 64.5)
    # L held high and R low, so the interleave has to produce a clean
    # 1.536 MHz square: anything else means the two channels are not landing
    # in alternate bit slots
    fd = freq(tt, w["pi_din"][sel], level=1.65)
    check("PI_DIN frequency (kHz)", fd / 1e3 if fd else None, 1528, 1544,
          " kHz")
    check("PI_DIN duty (%)", duty(tt, w["pi_din"][sel], level=1.65), 45, 55,
          " %")

    # the claim: DIN changes on a BCLK falling edge and the Pi samples it on
    # the rising one, so half a BCLK period -- 163 ns -- is the setup margin.
    # Skew eats into it, and only the DIFFERENCE between the two paths counts.
    din = np.sort(np.concatenate([edges(tt, w["pi_din"][sel], 1.65, True),
                                  edges(tt, w["pi_din"][sel], 1.65, False)]))
    clk = edges(tt, w["pi_bclk"][sel], 1.65, True)
    setup = []
    for e in din[2:-2]:
        nxt = clk[clk > e]
        if len(nxt):
            setup.append(nxt[0] - e)
    m = float(np.min(setup)) * 1e9 if setup else None
    report("worst data-to-clock setup", m or float("nan"), " ns")
    check("setup margin left after skew (ns)", m, 100, 200, " ns")


def bench_h():
    """The whole loop: does it survive a click, and where does it clamp?"""
    t0 = time.time()
    w = simulate(netlist("sim_h_loop"))
    print(f"    (transient took {time.time() - t0:.0f} s)")
    t = w["time"]
    i1, i2, i3 = w["int1"], w["int2"], w["int3"]
    q, sumn = w["ql"], w["sum1"]

    # settled, before the click at 1.5 ms
    pre = window(t, 0.8e-3, 1.4e-3)
    for name, v, want in (("INT1", i1, 1.43), ("INT2", i2, 1.47),
                          ("INT3", i3, 1.45)):
        pk = float(np.abs(v[pre]).max())
        report(f"{name} peak at -8 dBFS", pk, " V")
        check(f"{name} swing matches design-notes (V)", pk, want * 0.7,
              want * 1.4, " V")

    # the modulator has to be modulating, not stuck
    dpre = float((q[pre] > 2.5).mean())
    check("output density before the click (%)", dpre * 100, 25, 75, " %")

    # THE CLICK TEST.  40 us at three times full scale, then it must come
    # back: a 1-bit third-order loop that overloads does not recover on its
    # own, and on a vinyl source that is not a corner case.
    post = window(t, 2.2e-3, 2.9e-3)
    dpost = float((q[post] > 2.5).mean())
    check("output density after the click (%)", dpost * 100, 25, 75, " %")
    for name, v, want in (("INT1", i1, 1.43), ("INT2", i2, 1.47),
                          ("INT3", i3, 1.45)):
        pk = float(np.abs(v[post]).max())
        check(f"{name} back to its normal swing after the click (V)", pk,
              want * 0.7, want * 1.5, " V")

    # where the op-amps actually saturate -- the clamp the design leans on
    during = window(t, 1.5e-3, 1.6e-3)
    for name, v in (("INT1", i1), ("INT2", i2), ("INT3", i3)):
        report(f"{name} clamp during the click, positive", float(v[during].max()), " V")
        report(f"{name} clamp during the click, negative", float(v[during].min()), " V")
    check("integrators stay inside the rails (V)",
          float(max(np.abs(i1).max(), np.abs(i2).max(), np.abs(i3).max())),
          0, 5.0, " V")
    # The TL07x's input common-mode range is spec'd as +/-11 V MIN and
    # -12 V TYP on +/-15 V rails -- V- + 4 V guaranteed, V- + 3 V typical.
    # The charge pump makes -3.87 V (sim_a_pump), so the GUARANTEED floor is
    # +0.13 V and every virtual earth on this board sits at 0 V.  Inside the
    # typical range, outside the guaranteed one, and the -1 V of margin the
    # design assumed from a nominal -5 V rail is not there.
    v_neg = float(w["-5v"].mean())
    lo = float(sumn[t > 50e-6].min())
    report("negative rail", v_neg, " V")
    report("TL074 guaranteed CM floor (V- + 4 V)", v_neg + 4.0, " V")
    report("TL074 typical CM floor (V- + 3 V)", v_neg + 3.0, " V")
    report("summing node minimum", lo, " V")
    check("summing node clears the TYPICAL CM floor (V)", lo, v_neg + 3.0,
          1.0, " V")


BENCHES = {"a": ("sim_a_pump", bench_a), "b": ("sim_b_reference", bench_b),
           "c": ("sim_c_clock", bench_c), "d": ("sim_d_integrator", bench_d),
           "e": ("sim_e_quantiser", bench_e), "f": ("sim_f_dac", bench_f),
           "g": ("sim_g_interface", bench_g), "h": ("sim_h_loop", bench_h)}

wanted = [a.lower()[0] for a in sys.argv[1:]] or list(BENCHES)
for key in wanted:
    name, fn = BENCHES[key]
    print(f"\n{name}")
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"    ERROR {type(e).__name__}: {str(e)[:200]}")
        RESULTS.append((False, name))

ok = sum(1 for r, _ in RESULTS if r)
print(f"\n{ok}/{len(RESULTS)} checks passed")
for good, name in RESULTS:
    if not good:
        print(f"   FAILED: {name}")
sys.exit(0 if ok == len(RESULTS) else 1)
