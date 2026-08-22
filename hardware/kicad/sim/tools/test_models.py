#!/usr/bin/env python
r"""Prove each behavioural model matches its datasheet before any sheet uses it.

Run with the miniconda interpreter that has PySpice + ngspice:

    C:\Users\Mads2\miniconda3\python.exe tools\test_models.py

A verification harness only -- the deliverable schematics run in KiCad's own
simulator.  This exists so a broken model is caught here rather than by
misreading a plot, and it is deliberately separate from run_sims.py: this file
checks the MODELS against their datasheets, that one checks the DESIGN against
docs/design-notes.md.  A model and a design check that shared an assumption
would agree with each other and both be wrong.
"""
import sys
from pathlib import Path

import numpy as np
from PySpice.Spice.NgSpice.Shared import NgSpiceShared

HERE = Path(__file__).resolve().parent
LIB = (HERE.parent / "models" / "vinyl_adc_sim.lib").as_posix()

NG = NgSpiceShared.new_instance(verbose=False)
RESULTS = []


def run(deck):
    try:
        NG.remove_circuit()
    except Exception:  # noqa: BLE001 - nothing loaded on the first call
        pass
    NG.load_circuit(deck)
    try:
        NG.run()
    except Exception:  # noqa: BLE001
        # ngspice returns a non-zero status whenever it had to fall back on
        # dynamic gmin stepping, which it does for any deck whose operating
        # point starts with an amplifier hard against its clamp -- and then
        # runs the analysis perfectly.  The plot is the real test, so read it
        # and let the emptiness check below decide.
        pass
    plot = NG.plot(None, NG.last_plot)
    w = {k.lower(): np.asarray(v.to_waveform()) for k, v in plot.items()}
    sweep = w.get("time", w.get("frequency"))
    if sweep is None or len(sweep) < 2:
        raise RuntimeError("analysis produced no data")
    return w


def check(name, got, lo, hi, unit=""):
    ok = got is not None and np.isfinite(got) and lo <= got <= hi
    RESULTS.append((ok, name))
    g = "None" if got is None else f"{got:.4g}"
    print(f"  {'PASS' if ok else 'FAIL'}  {name:46s} {g:>11}{unit}"
          f"   want {lo:g}..{hi:g}{unit}")


def edge_time(t, v, level, rising=True, after=0.0):
    """First time after `after` that v crosses `level`, interpolated."""
    for i in range(1, len(v)):
        if t[i] < after:
            continue
        a, b = v[i - 1], v[i]
        if (rising and a < level <= b) or (not rising and a > level >= b):
            f = (level - a) / (b - a) if b != a else 0.0
            return t[i - 1] + f * (t[i] - t[i - 1])
    return None


def edges(t, v, level, rising=True):
    """Every crossing of `level`, interpolated."""
    out = []
    for i in range(1, len(v)):
        a, b = v[i - 1], v[i]
        if (rising and a < level <= b) or (not rising and a > level >= b):
            f = (level - a) / (b - a) if b != a else 0.0
            out.append(t[i - 1] + f * (t[i] - t[i - 1]))
    return np.array(out)


def duty(t, v, level):
    """Duty cycle from edge crossings, in percent.

    Not from the fraction of SAMPLES above the threshold: with a fixed step
    and a window that is not a whole number of periods, that reads several
    percent off on a slow output -- which looks exactly like a broken divider.
    """
    up, dn = edges(t, v, level, True), edges(t, v, level, False)
    if len(up) < 3 or len(dn) < 3:
        return None
    period = float(np.mean(np.diff(up)))
    dn = dn[dn > up[0]]
    n = min(len(up), len(dn))
    return float(np.mean(dn[:n] - up[:n])) / period * 100.0


# =========================================================== OPAMP_TL074 ====
print("\nOPAMP_TL074   (TI SLOS080: GBW 3 MHz, SR 13 V/us, Avol 200 V/mV)")

# Open loop, with a DC-only feedback path so the bias point is mid-rail and
# the AC input still sees an open loop.  Without it the operating point sits
# on the output clamp and .ac linearises the flat branch -- zero gain.
w = run(f"""* TL074 open-loop gain and bandwidth
.include "{LIB}"
Vp vp 0 5
Vn vn 0 -5
Vin inp 0 DC 0 AC 1
X1 inp inn out vp vn OPAMP_TL074
Lf out inn 1e9
Cf inn 0 1e9
Rl out 0 10k
.ac dec 20 0.1 100meg
.end
""")
f, g = np.abs(w["frequency"]), np.abs(w["out"])
check("open-loop DC gain (dB)", 20 * np.log10(g[0]), 95, 105, " dB")
# unity-gain crossing == gain-bandwidth product for a one-pole amplifier
i = np.argmin(np.abs(g - 1.0))
check("gain-bandwidth product (MHz)", f[i] / 1e6, 2.7, 3.3, " MHz")

w = run(f"""* TL074 slew rate and output saturation, unity-gain follower
.include "{LIB}"
Vp vp 0 5
Vn vn 0 -5
* step well past the output clamp so the amp slews all the way and then sticks
Vin inp 0 PULSE(-4 4 1u 1n 1n 10u 20u)
X1 inp out out vp vn OPAMP_TL074
Rl out 0 10k
.tran 5n 12u
.end
""")
t, o = w["time"], w["out"]
t1 = edge_time(t, o, -1.0, rising=True)
t2 = edge_time(t, o, 1.0, rising=True)
check("slew rate (V/us)", 2.0 / (t2 - t1) / 1e6 if t1 and t2 else None,
      11, 15, " V/us")
# 5 V rails less 1.5 V of headroom
check("positive output clamp (V)", float(o[(t > 8e-6)].max()), 3.3, 3.7, " V")
check("negative output clamp (V)", float(o[(t > 0.5e-6) & (t < 1e-6)].min()),
      -3.7, -3.3, " V")

# =========================================================== CMP_LM311 ======
print("\nCMP_LM311   (TI SLCS007: response 200 ns, VOL 0.23 V at 8 mA)")
w = run(f"""* LM311 on a single 5 V supply, threshold at 2.5 V, 2k21 pull-up
.include "{LIB}"
Vp vp 0 5
Vth inn 0 2.5
Vin inp 0 PULSE(2.4 2.6 1u 1n 1n 2u 8u)
X1 inp inn out 0 vp 0 CMP_LM311
Rpu vp out 2k21
.tran 5n 6u
.end
""")
t, o = w["time"], w["out"]
# NON-inverting: + rising above - drives the output HIGH
check("output high, + above - (V)", float(o[(t > 2e-6) & (t < 2.5e-6)].mean()),
      4.8, 5.05, " V")
check("output low, + below - (V)", float(o[(t > 4e-6) & (t < 4.8e-6)].mean()),
      0, 0.35, " V")
t_in = 1e-6
t_out = edge_time(t, o, 2.5, rising=True, after=t_in)
check("propagation delay (ns)", (t_out - t_in) * 1e9 if t_out else None,
      170, 230, " ns")
# VOL at 8 mA needs a stiffer pull-up than the board's; 620R draws ~8 mA
w = run(f"""* LM311 VOL at 8 mA
.include "{LIB}"
Vp vp 0 5
Vth inn 0 2.5
Vin inp 0 2.4
X1 inp inn out 0 vp 0 CMP_LM311
Rpu vp out 620
.tran 100n 4u
.end
""")
check("VOL at ~8 mA (V)", float(w["out"][-1]), 0.15, 0.30, " V")

# =========================================================== INV_74HC =======
print("\nINV_74HC   (74HC04 at 5 V: tpd 9 ns, Ron ~50 ohm)")
w = run(f"""* 74HC04 inversion, delay and output resistance
.include "{LIB}"
Vcc vcc 0 5
Vin in 0 PULSE(0 5 100n 1n 1n 200n 400n)
X1 in out vcc 0 INV_74HC
Rl out 0 1e9
* a second gate loaded with 1k reads the output resistance off the divider
X2 in outl vcc 0 INV_74HC
Rload outl 0 1k
.tran 200p 400n
.end
""")
t, o, ol = w["time"], w["out"], w["outl"]
check("output low after a high input (V)",
      float(o[(t > 250e-9) & (t < 290e-9)].mean()), 0, 0.02, " V")
check("output high after a low input (V)",
      float(o[(t > 50e-9) & (t < 90e-9)].mean()), 4.98, 5.02, " V")
t_out = edge_time(t, o, 2.5, rising=False, after=100e-9)
check("propagation delay (ns)", (t_out - 100e-9) * 1e9 if t_out else None,
      7, 12, " ns")
vh = float(ol[(t > 50e-9) & (t < 90e-9)].mean())
check("output resistance into 1k (ohm)", 1000.0 * (5.0 - vh) / vh, 40, 60, " ohm")

# =========================================================== NAND2_HCT132 ===
print("\nNAND2_74HCT132   (HCT threshold ~1.3 V, tpd 13 ns at 5 V)")
w = run(f"""* both inputs tied: a clock buffer.  Driven from 3.3 V, which is the
* whole reason the board fits an HCT part here -- a plain 74HC would want
* 3.5 V to be sure of a high.
.include "{LIB}"
Vcc vcc 0 5
Vin in 0 PULSE(0 3.3 100n 2n 2n 200n 400n)
X1 in in y vcc 0 NAND2_74HCT132
Rl y 0 1e9
.tran 200p 500n
.end
""")
t, y = w["time"], w["y"]
check("3.3 V input still swings the output (Vpp)",
      float(y.max() - y.min()), 4.9, 5.05, " Vpp")
check("inverts a high input (V)",
      float(y[(t > 250e-9) & (t < 290e-9)].mean()), 0, 0.02, " V")
t_y = edge_time(t, y, 2.5, rising=False, after=100e-9)
# the input crosses 1.3 V partway up its 2 ns edge, so allow for that
check("propagation delay (ns)", (t_y - 100e-9) * 1e9 if t_y else None,
      11, 17, " ns")

# =========================================================== BUF8_74HC244 ===
print("\nBUF8_74HC244   (8 sections paralleled: ~30/8 = 3.75 ohm)")
w = run(f"""* all eight outputs tied together and loaded, /OE low
.include "{LIB}"
Vcc vcc 0 5
Vin in 0 5
X1 0 in in in in y y y y 0 in in in in y y y y vcc 0 BUF8_74HC244
Rl y 0 100
.tran 10n 2u
.end
""")
vy = float(w["y"][-1])
check("paralleled output resistance (ohm)", 100.0 * (5.0 - vy) / vy, 3.0, 4.6,
      " ohm")
w = run(f"""* /OE high must tri-state, not drive
.include "{LIB}"
Vcc vcc 0 5
Vin in 0 5
X1 vcc in in in in y y y y vcc in in in in y y y y vcc 0 BUF8_74HC244
Rl y 0 100
.tran 10n 2u
.end
""")
check("tri-stated output (V)", float(w["y"][-1]), -0.01, 0.01, " V")

# =========================================================== DIV_74HC4040 ===
print("\nDIV_74HC4040   (ripple counter, counts on the CLK falling edge)")
w = run(f"""* 6.144 MHz in; watch Q0, Q1, Q4 and Q6 -- the four the board uses
.include "{LIB}"
Vdd vdd 0 5
Vmr mr 0 PULSE(5 0 200n 1n 1n 100 200)
Vclk clk 0 PULSE(0 5 0 2n 2n 79.35n 162.76n)
X1 clk mr q0 q1 q2 q3 q4 q5 q6 vdd 0 DIV_74HC4040
Rl0 q0 0 1e9
Rl1 q1 0 1e9
Rl2 q2 0 1e9
Rl3 q3 0 1e9
Rl4 q4 0 1e9
Rl5 q5 0 1e9
Rl6 q6 0 1e9
.tran 1n 60u
.end
""")
t = w["time"]
sel = t > 5e-6
for q, want, tol in (("q0", 3.072e6, 0.02), ("q1", 1.536e6, 0.02),
                     ("q4", 192e3, 0.02), ("q6", 48e3, 0.02)):
    e = edges(t[sel], w[q][sel], 2.5, rising=True)
    fq = 1.0 / np.mean(np.diff(e)) if len(e) > 2 else None
    check(f"{q.upper()} frequency (kHz)", fq / 1e3 if fq else None,
          want * (1 - tol) / 1e3, want * (1 + tol) / 1e3, " kHz")
# duty: every stage of a ripple counter divides by two, so all are 50 %
for q in ("q0", "q1", "q4"):
    check(f"{q.upper()} duty (%)", duty(t[sel], w[q][sel], 2.5), 49, 51, " %")

# =========================================================== DFF_74HC74 =====
print("\nDFF_74HC74   (positive edge, tpd 14 ns at 5 V)")
w = run(f"""* D changes between clock edges; Q must follow only on the rising edge
.include "{LIB}"
Vcc vcc 0 5
Vd d 0 PULSE(0 5 300n 1n 1n 600n 1200n)
Vclk clk 0 PULSE(0 5 0 1n 1n 250n 500n)
X1 d clk vcc vcc q qn vcc 0 DFF_74HC74
Rq q 0 1e9
Rqn qn 0 1e9
.tran 500p 3u
.end
""")
t, q, qn, d = w["time"], w["q"], w["qn"], w["d"]
# D goes high at 300 ns; the next rising clock edge is at 500 ns
t_q = edge_time(t, q, 2.5, rising=True, after=400e-9)
check("Q rises on the clock edge, not on D (ns)",
      (t_q - 500e-9) * 1e9 if t_q else None, 10, 20, " ns")
check("Q and ~Q are complementary (max sum error, V)",
      float(np.max(np.abs(q + qn - 5.0))[()]), 0, 0.6, " V")
w = run(f"""* asynchronous reset, active low
.include "{LIB}"
Vcc vcc 0 5
Vd d 0 5
Vclk clk 0 PULSE(0 5 0 1n 1n 250n 500n)
Vrn rn 0 PULSE(5 0 1.2u 1n 1n 1u 10u)
X1 d clk vcc rn q qn vcc 0 DFF_74HC74
Rq q 0 1e9
Rqn qn 0 1e9
.tran 500p 2u
.end
""")
t, q = w["time"], w["q"]
check("Q forced low by ~R (V)", float(q[(t > 1.5e-6) & (t < 2e-6)].mean()),
      0, 0.05, " V")

# =========================================================== MUX2_74HC157 ===
print("\nMUX2_74HC157   (S low selects I0, tpd 12 ns at 5 V)")
w = run(f"""* I0 held low, I1 held high, so Z simply follows S
.include "{LIB}"
Vcc vcc 0 5
Vi0 i0 0 0
Vi1 i1 0 5
Vs s 0 PULSE(0 5 100n 1n 1n 200n 400n)
X1 s i0 i1 z 0 vcc 0 MUX2_74HC157
Rz z 0 1e9
.tran 200p 500n
.end
""")
t, z = w["time"], w["z"]
check("S low selects I0 (V)", float(z[(t > 50e-9) & (t < 90e-9)].mean()),
      0, 0.02, " V")
check("S high selects I1 (V)", float(z[(t > 250e-9) & (t < 290e-9)].mean()),
      4.98, 5.02, " V")
t_z = edge_time(t, z, 2.5, rising=True, after=100e-9)
check("select-to-output delay (ns)", (t_z - 100e-9) * 1e9 if t_z else None,
      9, 15, " ns")
w = run(f"""* the active-low enable forces the output low
.include "{LIB}"
Vcc vcc 0 5
Vi1 i1 0 5
Vs s 0 5
X1 s 0 i1 z vcc vcc 0 MUX2_74HC157
Rz z 0 1e9
.tran 10n 500n
.end
""")
check("disabled output (V)", float(w["z"][-1]), 0, 0.02, " V")

# =========================================================== D1N5817 ========
print("\nD1N5817   (Vishay: 0.32 V at 100 mA, 0.45 V max at 1 A)")
w = run(f"""* forward drop at the pump's working current and at full rating
.include "{LIB}"
I1 0 a 32m
D1 a 0 D1N5817
I2 0 b 1
D2 b 0 D1N5817
.op
.tran 1u 10u
.end
""")
check("Vf at 32 mA (V)", float(w["a"][-1]), 0.20, 0.30, " V")
check("Vf at 1 A (V)", float(w["b"][-1]), 0.35, 0.48, " V")

# ============================================================================
ok = sum(1 for r, _ in RESULTS if r)
print(f"\n{ok}/{len(RESULTS)} model checks passed")
for good, name in RESULTS:
    if not good:
        print(f"   FAILED: {name}")
sys.exit(0 if ok == len(RESULTS) else 1)
