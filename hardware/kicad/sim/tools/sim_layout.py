#!/usr/bin/env python3
r"""Generate the SPICE testbenches for the discrete delta-sigma vinyl ADC.

    py -3.13 tools\sim_layout.py [bench ...]

One KiCad sheet per block of the board plus one for the whole modulator loop,
each its own project so the simulator has somewhere to keep its settings.
Open a .kicad_pro and press Run in Inspect -> Simulator; every sheet carries
its analysis command as text and in its .wbk workbook.

The blocks are imported from the BOARD's own layout script and called with the
bench's sheet, so the charge pump, the reference, the divider, every summing
stage and the quantiser are the same drawing here as they are on
vinyl_adc.kicad_sch.  A block wired one way on the board and another way in its
own testbench proves nothing, and the only way to guarantee they agree is to
call one function from both.

What SPICE is for here is the analog reality the Python model in ../../../sim
idealises: op-amp bandwidth and saturation, the comparator's 200 ns, the
charge pump under load, the DAC's output resistance.  It is NOT for the SNR
figure -- 68 dB over a 20 kHz band at OSR 32 needs about a second of transient
at nanosecond steps, which would run for hours and tell you what
sim/verify.py already knows.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(r"C:\Users\Mads2\.claude\skills\kicad-schematic\scripts")
sys.path.insert(0, str(SKILL))

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
KICAD = SIM.parent
sys.path.insert(0, str(KICAD / "tools"))

from schdraw import Sheet                                        # noqa: E402
from symcache import SymCache                                    # noqa: E402
from simfields import (add_hrefs, set_sim, src, subckt,           # noqa: E402
                       write_sym_lib_table, write_workbook)
import vinyl_adc_layout as board                                 # noqa: E402
from vinyl_adc_layout import (G, C_LIB, R_LIB, STUB,             # noqa: E402
                              charge_pump, clock_divider, front_end,
                              note_block, quantiser, reference, refs_for,
                              summing_stage, tie_low)

MODELS = "models/vinyl_adc_sim.lib"

# stock symbols
OPA = "Simulation_SPICE:OPAMP"
VDC = "Simulation_SPICE:VDC"
VSIN = "Simulation_SPICE:VSIN"
VPULSE = "Simulation_SPICE:VPULSE"
CMP = "Comparator:LM311"
MUX = "74xx:74LS157"
# vendored, because KiCad's SPICE exporter has no notion of symbol units: a
# multi-unit part exports as one broken device per reference, so every gate a
# bench simulates needs a single-unit symbol carrying its own supply pins
INV = "vinyl_adc_sim:INV_SIM"
NAND = "vinyl_adc_sim:NAND2_SIM"
DFF = "vinyl_adc_sim:DFF_SIM"

# Sim.Pins maps the SYMBOL's pin NUMBERS onto the subcircuit's node names.
SIM_OPAMP = subckt(MODELS, "OPAMP_TL074", "1=inp 2=inn 5=out 3=vp 4=vn")
SIM_LM311 = subckt(MODELS, "CMP_LM311", "2=inp 3=inn 7=out 1=oe 8=vp 4=vn")
SIM_HC04 = subckt(MODELS, "INV_74HC", "1=in 2=out 3=vcc 4=vss",
                  tpd="9n", ron="50")
SIM_HC4049 = subckt(MODELS, "INV_74HC", "1=in 2=out 3=vcc 4=vss",
                    tpd="25n", ron="100")
SIM_HCT132 = subckt(MODELS, "NAND2_74HCT132", "1=a 2=b 3=y 14=vcc 7=vss")
SIM_DFF = subckt(MODELS, "DFF_74HC74",
                 "2=d 3=clk 4=sn 1=rn 5=q 6=qn 14=vcc 7=vss")
SIM_MUX = subckt(MODELS, "MUX2_74HC157",
                 "1=s 2=i0 3=i1 4=z 15=e 16=vcc 8=vss")
# a1..a4 pair with y1..y4 and b1..b4 with z1..z4, section by section: get the
# pairing wrong and eight buffers still simulate, driving nothing
SIM_244 = subckt(MODELS, "BUF8_74HC244",
                 "1=oe1 2=a1 4=a2 6=a3 8=a4 18=y1 16=y2 14=y3 12=y4 "
                 "19=oe2 17=b1 15=b2 13=b3 11=b4 3=z1 5=z2 7=z3 9=z4 "
                 "20=vcc 10=vss")
SIM_4040 = subckt(MODELS, "DIV_74HC4040",
                  "10=clk 11=mr 9=q0 7=q1 6=q2 5=q3 3=q4 2=q5 4=q6 "
                  "16=vdd 8=vss")
SIM_DIODE = {"Sim.Device": "D", "Sim.Library": MODELS,
             "Sim.Name": "D1N5817", "Sim.Pins": "1=K 2=A"}

# The clocks, in one place, because several sheets and run_sims.py all need
# the same periods and a hand-typed 651.04n in two files is a bug waiting.
F_OSC = 6.144e6
T_OSC = 1.0 / F_OSC                    # 162.760 ns
T_MCLK = 4.0 / F_OSC                   # 651.042 ns, the modulator clock
T_PUMP = 32.0 / F_OSC                  # 5.208 us, the charge-pump drive


def ns(t):
    return f"{t * 1e9:.4g}n"


def us(t):
    return f"{t * 1e6:.6g}u"


# The analysis each sheet runs and what to plot: one source of truth for the
# text on the sheet, the .wbk the simulator opens with, and run_sims.py.
WORKBOOK = {
    "sim_a_pump": (".tran 200n 80m",
                   ["V(/-5V)", "V(/PUMPNODE)"]),
    "sim_b_reference": (".tran 2u 3m",
                        ["V(/VREF_P)", "V(/VREF_N)", "V(/+5V)/2"]),
    "sim_c_clock": (".tran 1n 60u uic",
                    ["V(/BCLK)", "V(/MCLK)", "V(/LRCLK)"]),
    "sim_d_integrator": (".tran 5n 80u uic",
                         ["V(/INT1)", "V(/SUM1)", "V(/DACN_L)"]),
    "sim_e_quantiser": (".tran 20n 1m uic",
                        ["V(/CMP_L)", "V(/SUMC)", "V(/V3)"]),
    "sim_f_dac": (".tran 5n 40u uic",
                  ["V(/INT1)", "V(/DACN_L)", "V(/DACP_L)"]),
    "sim_g_interface": (".tran 2n 100u uic",
                        ["V(/PI_DIN)", "V(/PI_BCLK)", "V(/PI_LRCLK)"]),
    "sim_h_loop": (".tran 10n 3m uic",
                   ["V(/INT1)", "V(/INT3)", "V(/QL)", "V(/WIPER)"]),
}

BENCHES = []


def bench(name, title, uuid, paper="A3"):
    def deco(fn):
        BENCHES.append((name, title, uuid, paper, fn))
        return fn
    return deco


# ------------------------------------------------------------------ helpers
def new_sheet(title, project, uuid, paper):
    sh = Sheet(paper=paper, title=title, project=project, version=10,
               uuid=uuid)
    sh.src._cache = SymCache(extra_dirs=[str(SIM / "lib")])
    return sh


def dc_supply(sh, sim, ref, x, y, volts, net, gnd_flag=True):
    """A bench rail: one VDC, its rail symbol, and the PWR_FLAG ERC wants.

    Exactly ONE flag per net on a sheet: two of them are two Power OUTPUT
    pins driving each other, which ERC reports as a pin conflict.
    """
    v = sh.place(VDC, ref, at=(x, y), value=str(volts))
    sim[ref] = src("DC", f"dc={volts}")
    up, dn = v.pin(1), v.pin(2)
    sh.rail(up, net=net, rise=STUB)
    sh.gnd(dn, drop=STUB)
    sh.seg(up, (x + G(8), up.y))
    sh.power("power:PWR_FLAG", (x + G(8), up.y))
    if gnd_flag:
        sh.seg(dn, (x + G(8), dn.y))
        sh.power("power:PWR_FLAG", (x + G(8), dn.y))
    return v


def source(sh, sim, lib, ref, x, y, params, value=""):
    """A stimulus source, grounded at the bottom.  The caller wires pin 1.

    Deliberately NOT a global label: on a bench the source sits next to the
    pin it drives, which makes it a wire, not a long haul.  Labelling it
    instead is the label-soup failure this whole toolkit exists to stop.
    """
    v = sh.place(lib, ref, at=(x, y), value=value)
    sim[ref] = src(*params)
    sh.gnd(v.pin(2), drop=STUB)
    return v


def labelled_source(sh, sim, lib, ref, x, y, name, params, value=""):
    """A source whose top pin becomes a named net.

    Only for nets that genuinely fan out across a sheet -- VREF_N reaches six
    resistors on the loop bench, MCLK three.  Anything with one destination
    gets source() and a drawn wire instead.
    """
    v = sh.place(lib, ref, at=(x, y), value=value)
    sim[ref] = src(*params)
    sh.seg(v.pin(1), (x, y - G(8)))
    sh.label((x, y - G(8)), name, kind="global")
    sh.gnd(v.pin(2), drop=STUB)
    return v


def term_bus(sh, items, x0, y0, ref0, pitch=G(8), value="1M0"):
    """Terminate each (point, name) in its own resistor, on one ground rail.

    Every output needs a load and every node needs a DC path -- and the point
    nearest the termination row takes the nearest column, so no run crosses
    another.  Names go on the wire, not on a bare stub, so the net is a real
    two-pin net that happens to be named.
    """
    items = sorted(items, key=lambda it: -it[0][1])
    xs = []
    for i, (pt, name) in enumerate(items):
        x = x0 + i * pitch
        xs.append(x)
        sh.seg(pt, (x, pt[1]))
        sh.seg((x, pt[1]), (x, y0))
        r = sh.place(R_LIB, f"{ref0}{i + 1}", at=(x, y0 + G(3)), rot=0,
                     value=value)
        sh.seg((x, y0), r.pin(1))
        sh.seg(r.pin(2), (x, y0 + G(6)))
        if name:
            sh.label((x, pt[1]), name, kind="global")
    sh.seg((xs[0], y0 + G(6)), (xs[-1], y0 + G(6)))
    sh.gnd(((xs[0] + xs[-1]) / 2, y0 + G(6)))
    return xs


def opamp_rails(sh, u):
    """Take a Simulation_SPICE:OPAMP section's V+/V- out to the rails.

    The board hangs one TL074 power unit off the package instead, which a
    SPICE netlist cannot express -- KiCad's exporter has no notion of symbol
    units -- so each bench section carries its own supply pins.
    """
    vp, vn = u.pin("V+"), u.pin("V-")
    sh.rail(vp, net="+5V", rise=STUB)
    sh.seg(vn, (vn.x, vn.y + STUB))
    sh.rail((vn.x, vn.y + STUB), net="-5V", rise=-STUB)


def gate(sh, sim, ref, x, y, fields, value, vcc="+5V"):
    """One INV_SIM section with its supplies wired.

    Rows of these must be at least G(24) apart: the VCC rail symbol sits
    12.7 mm above the gate and the GND symbol 12.7 mm below, so gates any
    closer put a +5 V symbol exactly on top of a GND symbol -- which ERC
    reports as "+5V and GND attached to the same items" and is a dead short.
    """
    u = sh.place(INV, ref, at=(x, y), value=value)
    sim[ref] = dict(fields)
    sh.rail(u.pin("VCC"), net=vcc, rise=STUB)
    sh.gnd(u.pin("GND"), drop=STUB)
    return u


def elbow_to(sh, a, b, xmid=None, ymid=None):
    """Route a -> b, either through a vertical at xmid or a horizontal at ymid."""
    ax, ay = a if isinstance(a, tuple) else (a.x, a.y)
    bx, by = b if isinstance(b, tuple) else (b.x, b.y)
    if ymid is not None:
        sh.seg((ax, ay), (ax, ymid))
        sh.seg((ax, ymid), (bx, ymid))
        sh.seg((bx, ymid), (bx, by))
    else:
        xm = xmid if xmid is not None else bx
        sh.seg((ax, ay), (xm, ay))
        sh.seg((xm, ay), (xm, by))
        sh.seg((xm, by), (bx, by))


# IEC 60062 letter-and-digit notation is right for a BOM and unreadable to
# SPICE.  ngspice takes the leading number, looks for a scale suffix and
# throws the rest away, so on this board:
#
#     14k7 -> 14 k        (the .7 silently dropped, 5 % low)
#     5k90 ->  5 k        (15 % low)
#     4R75 ->  4 ohm
#     1M0  ->  1 MILLIOHM (SPICE's M is milli, not mega -- a dead short)
#
# Nothing warns.  The deck exports, the sim runs, and it is a different
# circuit.  So every passive gets a Sim.Params override carrying the same
# value spelled the way ngspice reads it, while the Value field keeps the
# notation the board and the BOM use.
IEC_MULT = {"R": 1.0, "r": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9,
            "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12}


def iec_value(text):
    """'14k7' -> 14700.0, '4R75' -> 4.75, '220p' -> 2.2e-10."""
    t = str(text).strip()
    for i, ch in enumerate(t):
        if ch in IEC_MULT and i > 0:
            head, tail = t[:i], t[i + 1:]
            frac = f".{tail}" if tail and tail.isdigit() else ""
            return float(head + frac) * IEC_MULT[ch]
    return float(t)


PASSIVE = {"Device:R": ("R", "r"), "Device:C": ("C", "c"),
           "Device:C_Polarized": ("C", "c"),
           "Device:R_Potentiometer_Trim": (None, None)}


def passive_sims(sh):
    """Sim fields for every passive whose value SPICE would misread."""
    out = {}
    for part in sh.parts:
        dev, key = PASSIVE.get(part.lib_id, (None, None))
        if not dev or not part.value:
            continue
        try:
            v = iec_value(part.value)
        except ValueError:
            continue
        out[part.ref] = {"Sim.Device": dev, "Sim.Pins": "1=+ 2=-",
                         "Sim.Params": f"{key}={v:.6g}"}
    return out


def cmd_note(sh, name, at):
    note_block(sh, at, WORKBOOK[name][0], size=1.6)


def back_link(sh, y):
    text = "<-  back to the board schematic   vinyl_adc.kicad_sch"
    sh.note((G(10), y), text, size=1.6)
    return {text: "file:../vinyl_adc.kicad_sch"}


# ===========================================================================
# A  rails and the -5 V charge pump
# ===========================================================================
@bench("sim_a_pump", "A - rails and the -5 V charge pump",
       "b1000000-0000-4000-8000-000000000001")
def build_a(sh):
    sim = {}
    note_block(sh, (G(10), G(8)),
               "A  The -5 V charge pump  (74HC244 x8 paralleled, "
               "192 kHz, loaded at 32 mA)", size=2.0)

    dc_supply(sh, sim, "V1", G(14), G(26), 5, "+5V")
    v2 = source(sh, sim, VPULSE, "V2", G(14), G(56),
                ("PULSE", f"y1=0 y2=5 td=0 tr=5n tf=5n "
                          f"tw={ns(T_PUMP / 2)} per={ns(T_PUMP)}"))
    sh.seg(v2.pin(1), (G(14), G(44)))
    sh.label((G(14), G(44)), "PUMP", kind="global")
    note_block(sh, (G(8), G(72)),
               "PUMP is 4040 Q4 = 192 kHz, which is 4x the 48 kHz output\n"
               "rate on purpose: whatever ripple survives lands exactly on a\n"
               "null of the CIC decimator.  sim_c_clock makes it for real.",
               size=1.27)

    pump = charge_pump(sh, G(60), G(28))
    sim["U1"] = dict(SIM_244)
    sim["D1"] = dict(SIM_DIODE)
    sim["D2"] = dict(SIM_DIODE)

    nx, cy = pump["node"]
    sh.seg((nx, cy), (nx + G(6), cy))
    sh.label((nx + G(6), cy), "PUMPNODE", kind="global")

    ox, oy = pump["out"]
    rl = sh.place(R_LIB, "RL1", at=(ox + G(10), oy + G(8)), rot=0,
                  value="130R")
    sh.seg((ox, oy), (ox + G(10), oy))
    sh.seg((ox + G(10), oy), rl.pin(1))
    sh.gnd(rl.pin(2), drop=STUB)
    # the -5 V net is made by passive parts, so nothing on it is a power
    # OUTPUT pin and ERC will not believe it is driven without this
    sh.seg((ox + G(10), oy), (ox + G(10), oy - G(6)))
    sh.power("power:PWR_FLAG", (ox + G(10), oy - G(6)))
    note_block(sh, (G(96), G(74)),
               "130R is the analog section: two TL074, a TL072 and the DAC\n"
               "offset legs, about 32 mA.  That current is the whole reason\n"
               "the comparators run on a single +5 V supply -- leaving them\n"
               "on the negative rail costs 8 mA and the TL074s then cannot\n"
               "clear their 1.94 V peak swing.", size=1.27)

    note_block(sh, (G(10), G(84)),
               "Measured: -3.87 V at 29.8 mA, settling in about 40 ms, with\n"
               "0.24 uV of ripple after 4R75 + 220u.  The design's \"under\n"
               "1 uV\" holds; its -4.1 V does not.\n"
               "The pump's output resistance is about 16 ohm and it is set by\n"
               "the 74HC244's own on-resistance, not by 1/fC: 10 uF through\n"
               "4 ohm is a 40 us time constant against a 2.6 us half period,\n"
               "so the flying cap never finishes charging.  A bigger C4 or a\n"
               "faster PUMP will not fix that; only more parallel buffers\n"
               "would -- and there are no more.\n"
               "The 40 ms matters at bring-up: measure the rail straight\n"
               "after power-on and it is still climbing.", size=1.27)
    cmd_note(sh, "sim_a_pump", (G(10), G(106)))
    return sim


# ===========================================================================
# B  the +/-2.5 V ratiometric reference
# ===========================================================================
@bench("sim_b_reference", "B - the +/-2.5 V ratiometric reference",
       "b1000000-0000-4000-8000-000000000002")
def build_b(sh):
    sim = {}
    note_block(sh, (G(10), G(8)),
               "B  The +/-2.5 V DAC reference  (ratiometric: it TRACKS the "
               "+5 V rail on purpose)", size=2.0)

    # the +5 V rail carries a deliberate 100 mV of 1 kHz hum, which is the
    # whole test: VREF_P must stay at exactly half of it, moment by moment
    v1 = sh.place(VSIN, "V1", at=(G(14), G(26)), value="5 +/- 0.1")
    sim["V1"] = src("SIN", "dc=5 ampl=0.1 f=1k")
    sh.rail(v1.pin(1), net="+5V", rise=STUB)
    sh.gnd(v1.pin(2), drop=STUB)
    sh.seg(v1.pin(1), (G(22), v1.pin(1).y))
    sh.power("power:PWR_FLAG", (G(22), v1.pin(1).y))
    sh.seg(v1.pin(2), (G(22), v1.pin(2).y))
    sh.power("power:PWR_FLAG", (G(22), v1.pin(2).y))
    dc_supply(sh, sim, "V2", G(14), G(52), -5, "-5V", gnd_flag=False)

    note_block(sh, (G(8), G(66)),
               "The +5 V rail is given 100 mV of 1 kHz hum deliberately.\n"
               "Because the divider tracks the same rail the DAC gate swings\n"
               "between, that noise arrives as a common-mode GAIN modulation\n"
               "at -98 dB rather than as additive noise -- so VREF_P must\n"
               "stay at exactly half the rail, sample by sample.  Filtering\n"
               "the reference instead of tracking it would break the\n"
               "cancellation and inject the rail noise at full weight.",
               size=1.27)

    u2a, u2b = reference(sh, G(64), G(26), opamp=OPA,
                         refs=("U2A", "U2B"), supply=False)
    sim["U2A"] = dict(SIM_OPAMP)
    sim["U2B"] = dict(SIM_OPAMP)
    for u in (u2a, u2b):
        opamp_rails(sh, u)

    # the real load on VREF_N: six DAC offset legs, two channels
    rl = sh.place(R_LIB, "RL1", at=(G(172), G(78)), rot=0, value="1k87")
    sh.seg((G(164), G(74)), (G(172), G(74)))
    sh.label((G(164), G(74)), "VREF_N", kind="global")
    sh.seg((G(172), G(74)), rl.pin(1))
    sh.gnd(rl.pin(2), drop=STUB)
    note_block(sh, (G(140), G(88)),
               "1k87 is what six DAC offset legs (14k7, 13k0, 8k25, twice)\n"
               "look like from VREF_N.  VREF_P drives almost nothing: both\n"
               "ends of Rsh sit at +2.5 V, so no current flows in it.",
               size=1.27)
    cmd_note(sh, "sim_b_reference", (G(10), G(98)))
    return sim


# ===========================================================================
# C  the clock: 6.144 MHz in, four clocks out
# ===========================================================================
@bench("sim_c_clock", "C - clock buffer and 74HC4040 divider",
       "b1000000-0000-4000-8000-000000000003")
def build_c(sh):
    sim = {}
    note_block(sh, (G(10), G(8)),
               "C  Clock  (6.144 MHz -> BCLK 3.072M, MCLK 1.536M, "
               "PUMP 192k, LRCLK 48k)", size=2.0)

    dc_supply(sh, sim, "V1", G(14), G(26), 5, "+5V")
    # 3.3 V, not 5 V: the worst case the HCT buffer is fitted to survive
    v2 = source(sh, sim, VPULSE, "V2", G(34), G(54),
                ("PULSE", f"y1=0 y2=3.3 td=0 tr=3n tf=3n "
                          f"tw={ns(T_OSC / 2)} per={ns(T_OSC)}"),
                value="0-3.3V 6.144MHz")
    note_block(sh, (G(8), G(66)),
               "The source swings 0-3.3 V, which is the case the 74HCT132\n"
               "is fitted for: HCT switches near 1.3 V instead of at half\n"
               "supply, so a 3.3 V oscillator can -- or the Pi's GPCLK0 on\n"
               "the bring-up jumper -- still meets VIH into a 5 V chain.\n"
               "A plain 74HC here would want 3.5 V and might not switch.",
               size=1.27)

    u3 = sh.place(NAND, "U3", at=(G(60), G(34)), value="74HCT132")
    sim["U3"] = dict(SIM_HCT132)
    a, b = u3.pin("A"), u3.pin("B")
    tie_x = a.x - G(4)
    sh.seg(a, (tie_x, a.y))
    sh.seg(b, (tie_x, b.y))
    sh.seg((tie_x, a.y), (tie_x, b.y))
    sh.seg(v2.pin(1), (v2.x, a.y))
    sh.seg((v2.x, a.y), (tie_x, a.y))
    sh.label((v2.x + G(6), a.y), "OSC", kind="global")
    sh.rail(u3.pin("VCC"), net="+5V", rise=STUB)
    sh.gnd(u3.pin("GND"), drop=STUB)
    note_block(sh, (G(48), G(50)),
               "both inputs tied: a NAND used as the clock buffer", size=1.27)

    div = clock_divider(sh, G(112), G(30), clk_label=None, out_labels=False,
                        nc_spares=False, cap_x=G(86))
    sim["U4"] = dict(SIM_4040)
    elbow_to(sh, u3.pin("Y"), div["clk"], xmid=G(94))
    sh.label((G(94), u3.pin("Y").y), "CLK6M", kind="global")

    # every stage of the counter brought out, loaded and named: on a divider
    # bench the whole chain is the measurement
    named = {9: "BCLK", 7: "MCLK", 3: "PUMP", 4: "LRCLK", 6: "Q2", 5: "Q3",
             2: "Q5", 13: "Q7", 12: "Q8", 14: "Q9", 15: "Q10", 1: "Q11"}
    u4 = div["u"]
    items = [((u4.pin(pin).x, u4.pin(pin).y), name)
             for pin, name in named.items()]
    term_bus(sh, items, G(140), G(64), "RT", pitch=G(6))

    note_block(sh, (G(10), G(84)),
               "Every output must be an exact binary division of 6.144 MHz\n"
               "at 50 % duty, and every one of them changes on a falling\n"
               "master-clock edge -- which is where the Pi's I2S setup\n"
               "margin comes from.  The ripple delay through the counter\n"
               "eats into that margin: Q0 is one stage from CLK and Q6 is\n"
               "seven, so watch the skew between BCLK and LRCLK, not just\n"
               "their frequencies.  sim_g_interface spends what is left.\n"
               "Every stage is loaded with 1M: an output with nothing on it\n"
               "tells you nothing, and every node wants a DC path.",
               size=1.27)
    cmd_note(sh, "sim_c_clock", (G(10), G(102)))
    return sim


# ===========================================================================
# D  one integrator, with a real TL074
# ===========================================================================
@bench("sim_d_integrator", "D - integrator 1 with a real TL074",
       "b1000000-0000-4000-8000-000000000004")
def build_d(sh):
    sim = {}
    r = refs_for("L", 20)
    note_block(sh, (G(10), G(8)),
               "D  Integrator 1  (a1 = 0.247, and where the TL074 really "
               "saturates)", size=2.0)

    dc_supply(sh, sim, "V1", G(14), G(26), 5, "+5V")
    dc_supply(sh, sim, "V2", G(14), G(52), -5, "-5V", gnd_flag=False)

    y = G(34)
    X = G(130)
    i1 = summing_stage(sh, X, y,
                       [(None, r["Rin"], "20k5"),
                        (None, r["Rd1"], "14k7"),
                        (None, r["Ro1"], "14k7")],
                       "U20", 1, "C", r["C1"], "220p", opamp=OPA,
                       title="INTEGRATOR 1  (a1 = 0.247)")
    sim["U20"] = dict(SIM_OPAMP)
    opamp_rails(sh, i1["u"])

    # a full-scale step at 40 us, to drive the integrator into saturation
    v3 = source(sh, sim, VPULSE, "V3", G(46), G(78),
                ("PULSE", "y1=0 y2=3.486 td=40u tr=100n tf=100n "
                          "tw=30u per=200u"), value="0-3.486V step")
    v4 = source(sh, sim, VPULSE, "V4", G(62), G(78),
                ("PULSE", f"y1=0 y2=5 td=0 tr=5n tf=5n "
                          f"tw={ns(T_MCLK)} per={ns(2 * T_MCLK)}"),
                value="0-5V 768kHz")
    v5 = source(sh, sim, VDC, "V5", G(78), G(78), ("DC", "dc=-2.5"),
                value="-2.5")
    # leftmost source takes the topmost row, so no run crosses another
    for v, row, name in ((v3, 0, "IN"), (v4, 1, "DACN_L"), (v5, 2, "VREF_N")):
        ry = y + row * board.COL
        sh.seg(v.pin(1), (v.x, ry))
        sh.seg((v.x, ry), (X, ry))
        sh.label((v.x + G(6), ry), name, kind="global")

    ox, oy = i1["out"]
    sh.seg((ox, oy), (ox + G(8), oy))
    sh.label((ox + G(4), oy), "INT1", kind="global")
    rl = sh.place(R_LIB, "RL1", at=(ox + G(8), oy + G(8)), rot=0, value="10k5")
    sh.seg((ox + G(8), oy), rl.pin(1))
    sh.gnd(rl.pin(2), drop=STUB)
    note_block(sh, (ox + G(2), oy + G(22)),
               "10k5 is what integrator 2's\ninput resistor looks like",
               size=1.27)
    # the virtual earth, named so a measurement can watch it against the
    # TL074's own input common-mode floor
    sh.label((X + G(21), y + board.COL), "SUM1", kind="global")

    note_block(sh, (G(10), G(92)),
               "The DAC toggles every clock period with the input at zero, so\n"
               "the output is a triangle whose peak-to-peak IS a1 x S1 =\n"
               "0.247 x 2.04 V = 0.503 V.  That is the loop coefficient read\n"
               "straight off the plot, with no arithmetic in between.",
               size=1.27)
    note_block(sh, (G(10), G(100)),
               "At 40 us the input steps to full scale (3.486 Vpk) and the\n"
               "integrator runs into its rail.  Where it stops is the number\n"
               "the whole design leans on: there are no clamp parts, and the\n"
               "op-amp's own saturation is the only thing that stops a vinyl\n"
               "click latching the modulator (docs/design-notes.md 4a).\n"
               "Watch SUM1 too: the TL074's input common-mode floor is\n"
               "V- + 4 V = -1 V on these rails, and the virtual earth is only\n"
               "a virtual earth while the amp is still in control.",
               size=1.27)
    cmd_note(sh, "sim_d_integrator", (G(10), G(118)))
    return sim


# ===========================================================================
# E  the quantiser
# ===========================================================================
@bench("sim_e_quantiser", "E - LM311 quantiser on a single supply",
       "b1000000-0000-4000-8000-000000000005")
def build_e(sh):
    sim = {}
    r = refs_for("L", 20)
    note_block(sh, (G(10), G(8)),
               "E  Quantiser  (LM311 on a single +5 V, threshold on VREF_P, "
               "and the ELD shift)", size=2.0)

    dc_supply(sh, sim, "V1", G(14), G(26), 5, "+5V")

    y = G(46)
    XC = G(130)
    q = quantiser(sh, XC, y, r, "L", rows_labelled=False)
    sim[r["Ucmp"]] = dict(SIM_LM311)

    # a slow triangle standing in for integrator 3's output, and the DAC
    # switched slowly so its two threshold positions can be told apart
    v2 = source(sh, sim, VSIN, "V2", G(46), G(90), ("SIN", "dc=0 ampl=1 f=20k"),
                value="1V 20kHz")
    v3 = source(sh, sim, VPULSE, "V3", G(64), G(90),
                ("PULSE", "y1=0 y2=5 td=0 tr=20n tf=20n tw=250u per=500u"),
                value="0-5V 1kHz")
    v4 = source(sh, sim, VDC, "V4", G(82), G(90), ("DC", "dc=2.5"),
                value="2.5")
    for v, row, name in ((v2, 0, "V3"), (v3, 1, "DACP_L"), (v4, 2, "VREF_P")):
        ry = y + row * board.COL
        sh.seg(v.pin(1), (v.x, ry))
        sh.seg((v.x, ry), (XC, ry))
        sh.label((v.x + G(6), ry), name, kind="global")
    # the comparator's + input takes the same +2.5 V, over the top
    px, py = q["plus"]
    sh.seg((v4.x, y + 2 * board.COL), (v4.x, py))
    sh.seg((v4.x, py), (px, py))
    sh.label((XC + G(21), y + board.COL), "SUMC", kind="global")

    note_block(sh, (G(10), G(108)),
               "Rb = Rs to +5 V is what centres the summing node on VREF_P:\n"
               "with the DAC at its mean the comparator switches at V3 = 0,\n"
               "so the quantiser's threshold costs no offset at all.\n"
               "Both LM311 inputs then sit at +2.5 V, comfortably inside its\n"
               "single-supply common-mode range of 0.5 V to V+ - 1.5 V.",
               size=1.27)
    note_block(sh, (G(10), G(118)),
               "Rk0 = 165k is the excess-loop-delay compensation.  It moves\n"
               "the threshold by +/-0.335 V of V3 as the DAC switches, which\n"
               "is |k0| = 0.335 / S3 = 0.335 / 1.47 = 0.228 -- the design's\n"
               "-0.225 as an E96 pair.  Without it the LM311's 200 ns costs\n"
               "8 dB and most of the overload margin.", size=1.27)
    cmd_note(sh, "sim_e_quantiser", (G(10), G(128)))
    return sim


# ===========================================================================
# F  the 1-bit DAC
# ===========================================================================
@bench("sim_f_dac", "F - the 1-bit DAC and its offset leg",
       "b1000000-0000-4000-8000-000000000006")
def build_f(sh):
    sim = {}
    r = refs_for("L", 20)
    note_block(sh, (G(10), G(8)),
               "F  The 1-bit DAC  (74HC04 into 14k7 and 13k0, recentred by "
               "equal legs to -2.5 V)", size=2.0)

    dc_supply(sh, sim, "V1", G(14), G(26), 5, "+5V")
    dc_supply(sh, sim, "V2", G(14), G(52), -5, "-5V", gnd_flag=False)

    v3 = source(sh, sim, VPULSE, "V3", G(40), G(40),
                ("PULSE", f"y1=0 y2=5 td=0 tr=5n tf=5n "
                          f"tw={ns(T_MCLK)} per={ns(2 * T_MCLK)}"),
                value="Q")
    v4 = source(sh, sim, VPULSE, "V4", G(40), G(74),
                ("PULSE", f"y1=5 y2=0 td=0 tr=5n tf=5n "
                          f"tw={ns(T_MCLK)} per={ns(2 * T_MCLK)}"),
                value="/Q")

    g1 = gate(sh, sim, "U7", G(70), G(40), SIM_HC04, "74HC04")
    g2 = gate(sh, sim, "U7B", G(70), G(74), SIM_HC04, "74HC04")
    sh.seg(v3.pin(1), (v3.x, g1.pin("A").y))
    sh.seg((v3.x, g1.pin("A").y), g1.pin("A"))
    sh.label((v3.x + G(6), g1.pin("A").y), "QL", kind="global")
    sh.seg(v4.pin(1), (v4.x, g2.pin("A").y))
    sh.seg((v4.x, g2.pin("A").y), g2.pin("A"))
    sh.label((v4.x + G(6), g2.pin("A").y), "QNL", kind="global")
    note_block(sh, (G(56), G(96)),
               "DACN from Q and DACP from /Q, so the two edges are as close\n"
               "to simultaneous as the parts allow.  Any asymmetry between\n"
               "them is DAC inter-symbol interference, which is the one\n"
               "mechanism that can make a 1-bit DAC non-linear -- and the\n"
               "one this model does not have (docs/design-notes.md 9).",
               size=1.27)

    y1, y2 = G(40), G(74)
    X = G(160)
    i1 = summing_stage(sh, X, y1, [(None, r["Rd1"], "14k7"),
                                   (None, r["Ro1"], "14k7")],
                       "U20", 1, "C", r["C1"], "220p", opamp=OPA,
                       title="INTO INTEGRATOR 1  (Rd = 14k7)")
    i2 = summing_stage(sh, X, y2, [(None, r["Rd2"], "13k0"),
                                   (None, r["Ro2"], "13k0")],
                       "U21", 1, "C", r["C2"], "220p", opamp=OPA,
                       title="INTO INTEGRATOR 2  (Rd = 13k0)", title_dy=G(-10))
    for st in (i1, i2):
        sim[st["u"].ref] = dict(SIM_OPAMP)
        opamp_rails(sh, st["u"])
    sh.seg(g1.pin("Y"), (X, y1))
    sh.label((g1.pin("Y").x + G(6), y1), "DACN_L", kind="global")
    sh.seg(g2.pin("Y"), (X, y2))
    sh.label((g2.pin("Y").x + G(6), y2), "DACP_L", kind="global")

    # one VREF_N source feeding both offset legs, as a drawn bus
    v5 = source(sh, sim, VDC, "V5", G(130), G(104), ("DC", "dc=-2.5"),
                value="-2.5")
    bus_x = X - G(4)
    sh.seg(v5.pin(1), (v5.x, y2 + board.COL))
    sh.seg((v5.x, y2 + board.COL), (bus_x, y2 + board.COL))
    sh.seg((bus_x, y2 + board.COL), (bus_x, y1 + board.COL))
    sh.seg((bus_x, y1 + board.COL), (X, y1 + board.COL))
    sh.seg((bus_x, y2 + board.COL), (X, y2 + board.COL))
    sh.label((bus_x, y1 + board.COL), "VREF_N", kind="global")

    for st, name in ((i1, "INT1"), (i2, "INT2")):
        ox, oy = st["out"]
        sh.seg((ox, oy), (ox + G(6), oy))
        sh.label((ox + G(3), oy), name, kind="global")
        rl = sh.place(R_LIB, f"RL{name[-1]}", at=(ox + G(6), oy + G(8)),
                      rot=0, value="10k5")
        sh.seg((ox + G(6), oy), rl.pin(1))
        sh.gnd(rl.pin(2), drop=STUB)

    note_block(sh, (G(10), G(116)),
               "The gate swings 0/5 V into Rd and an equal leg to -2.5 V\n"
               "recentres it, so the net feedback should be exactly +/-2.5 V\n"
               "-- which shows up as a triangle with equal up and down slopes\n"
               "of 2.5 / (Rd x 220p): 773 kV/s at integrator 1 and 874 kV/s\n"
               "at integrator 2.\n"
               "Any inequality between the two slopes is the 74HC04's own\n"
               "50 ohm of output resistance, which the ideal model in\n"
               "../../../sim does not have: it makes the high level\n"
               "5 x 14700/14750 rather than 5 V, so the two DAC levels are\n"
               "not quite symmetric about the reference.  That is a gain\n"
               "error and a DC offset, not distortion -- but it is worth\n"
               "knowing the size of it.", size=1.27)
    cmd_note(sh, "sim_f_dac", (G(10), G(142)))
    return sim


# ===========================================================================
# G  retime, interleave, level shift: the I2S the Pi actually sees
# ===========================================================================
@bench("sim_g_interface", "G - retiming, interleave and the 3.3 V level shift",
       "b1000000-0000-4000-8000-000000000007", paper="A2")
def build_g(sh):
    sim = {}
    note_block(sh, (G(10), G(8)),
               "G  The Pi interface  (retime -> interleave -> 3.3 V; "
               "is there any setup margin left?)", size=2.0)

    dc_supply(sh, sim, "V1", G(14), G(26), 5, "+5V")
    dc_supply(sh, sim, "V2", G(14), G(52), 3.3, "+3V3", gnd_flag=False)

    v3 = source(sh, sim, VPULSE, "V3", G(42), G(64),
                ("PULSE", f"y1=0 y2=5 td=0 tr=3n tf=3n "
                          f"tw={ns(T_OSC / 2)} per={ns(T_OSC)}"),
                value="6.144MHz")
    div = clock_divider(sh, G(74), G(30), clk_label=None, out_labels=True,
                        nc_spares=False, cap_x=G(48))
    sim["U4"] = dict(SIM_4040)
    elbow_to(sh, v3.pin(1), div["clk"], ymid=div["clk"].y)
    sh.label((v3.x, div["clk"].y), "CLK6M", kind="global")

    # PUMP and the eight stages this sheet does not use, terminated
    u4 = div["u"]
    spare_names = {6: "Q2", 5: "Q3", 2: "Q5", 13: "Q7", 12: "Q8", 14: "Q9",
                   15: "Q10", 1: "Q11"}
    items = [((u4.pin(p).x, u4.pin(p).y), n) for p, n in spare_names.items()]
    pump = div["outs"]["PUMP"]
    items.append(((pump.x + G(8), pump.y), None))   # already labelled
    term_bus(sh, items, G(102), G(80), "RT", pitch=G(6))

    # --- the two retiming flip-flops -------------------------------------
    qn_pts = []
    for i, ch in enumerate(("L", "R")):
        ref = f"U5{ch}"
        ff = sh.place(DFF, ref, at=(G(196), G(30) + i * G(34)),
                      value="74HC74")
        sim[ref] = dict(SIM_DFF)
        v = source(sh, sim, VDC, f"V{4 + i}", G(168),
                   G(30) + i * G(34) + G(16),
                   ("DC", f"dc={5 if ch == 'L' else 0}"),
                   value="5" if ch == "L" else "0")
        d, ck = ff.pin("D"), ff.pin("C")
        sh.seg(v.pin(1), (v.x, d.y))
        sh.seg((v.x, d.y), d)
        sh.label((v.x + G(6), d.y), f"CMP_{ch}", kind="global")
        sh.seg(ck, (ck.x - G(8), ck.y))
        sh.label((ck.x - G(8), ck.y), "MCLK", kind="global")
        q, qn = ff.pin("Q"), ff.pin("~{Q}")
        sh.seg(q, (q.x + G(8), q.y))
        sh.label((q.x + G(8), q.y), f"Q{ch}", kind="global")
        sh.seg(qn, (qn.x + G(4), qn.y))
        qn_pts.append(((qn.x + G(4), qn.y), f"QN{ch}"))
        for pn in ("~{S}", "~{R}"):
            p = ff.pin(pn)
            dy = -STUB if p.y < ff.y else STUB
            sh.seg(p, (p.x, p.y + dy))
            sh.rail((p.x, p.y + dy), net="+5V", rise=-dy if dy > 0 else STUB)
        sh.rail(ff.pin("VCC"), net="+5V", rise=STUB)
        sh.gnd(ff.pin("GND"), drop=STUB)
    term_bus(sh, qn_pts, G(216), G(80), "RQ", pitch=G(6))
    note_block(sh, (G(168), G(88)),
               "the D-FFs that put the DAC edges on the clock\n"
               "instead of on the comparator's own delay", size=1.27)

    # --- the interleave mux ----------------------------------------------
    mx = G(268)
    u6 = sh.place(MUX, "U6", at=(mx, G(44)), value="74HC157")
    sim["U6"] = dict(SIM_MUX)
    for pin, lbl in ((1, "MCLK"), (2, "QR"), (3, "QL")):
        p = u6.pin(pin)
        sh.seg(p, (p.x - G(7), p.y))
        sh.label((p.x - G(7), p.y), lbl, kind="global")
    sh.seg(u6.pin(4), (u6.pin(4).x + G(7), u6.pin(4).y))
    sh.label((u6.pin(4).x + G(7), u6.pin(4).y), "DIN", kind="global")
    tie_low(sh, u6.pin(15))
    tie_low(sh, *[u6.pin(n) for n in (5, 6, 10, 11, 13, 14)])
    for n in (7, 9, 12):
        sh.nc(u6.pin(n))
    sh.rail(u6.pin(16), net="+5V", rise=STUB)
    sh.gnd(u6.pin(8), drop=STUB)
    note_block(sh, (mx - G(16), G(14)),
               "MCLK selects: DIN carries R,L,R,L... at 3.072 Mbps.\n"
               "64 BCLK per LRCLK frame = 32 L bits + 32 R bits\n"
               "= exactly one OSR-32 sample per channel.", size=1.27)

    # --- level shift to 3.3 V --------------------------------------------
    lx = G(340)
    outs = []
    for i, sig in enumerate(("BCLK", "LRCLK", "DIN")):
        yy = G(28) + i * G(24)
        a = gate(sh, sim, f"U8{i}A", lx, yy, SIM_HC4049, "74HC4049",
                 vcc="+3V3")
        b = gate(sh, sim, f"U8{i}B", lx + G(20), yy, SIM_HC4049, "74HC4049",
                 vcc="+3V3")
        sh.seg(a.pin("A"), (a.pin("A").x - G(6), yy))
        sh.label((a.pin("A").x - G(6), yy), sig, kind="global")
        sh.seg(a.pin("Y"), b.pin("A"))
        outs.append(((b.pin("Y").x, yy), f"PI_{sig}"))
    term_bus(sh, outs, lx + G(34), G(88), "RP", pitch=G(6))
    note_block(sh, (lx - G(8), G(100)),
               "Two inverters per signal, not one.  The 74HC4049 tolerates\n"
               "an input above its own VCC -- it has no clamp diode to VCC --\n"
               "which is what makes the 5 V -> 3.3 V shift legal, but\n"
               "inverting BCLK would make the Pi sample on the data\n"
               "transition.  1M stands in for a GPIO input.", size=1.27)

    note_block(sh, (G(10), G(112)),
               "The claim under test: DIN changes on a BCLK falling edge and\n"
               "the Pi samples it on the rising one, so half a BCLK period --\n"
               "163 ns -- is the setup margin, with no retiming flip-flop\n"
               "needed anywhere.  What eats into it is skew: MCLK is one\n"
               "ripple stage further down the counter than BCLK, then the mux\n"
               "and two 4049 stages add their own, while PI_BCLK goes through\n"
               "two 4049 stages of its own.  Only the DIFFERENCE matters, and\n"
               "that is what this sheet measures.\n"
               "L is held high and R low, so DIN must come out as a clean\n"
               "1.536 MHz square: any other pattern means the two channels\n"
               "are not landing in alternate bit slots.", size=1.27)
    cmd_note(sh, "sim_g_interface", (G(10), G(134)))
    return sim


# ===========================================================================
# H  the whole modulator loop -- the sheet that answers the design question
# ===========================================================================
@bench("sim_h_loop", "H - one complete modulator channel, with the click test",
       "b1000000-0000-4000-8000-000000000008", paper="A2")
def build_h(sh):
    sim = {}
    r = refs_for("L", 20)
    r["RVb"] = "R39"
    note_block(sh, (G(10), G(8)),
               "H  One complete channel  -  3rd-order CT delta-sigma, "
               "fs 1.536 MHz, OSR 32", size=2.4)

    # ---- bench supplies --------------------------------------------------
    dc_supply(sh, sim, "V1", G(14), G(30), 5, "+5V")
    dc_supply(sh, sim, "V2", G(14), G(56), -3.87, "-5V",
              gnd_flag=False)
    labelled_source(sh, sim, VDC, "V3", G(40), G(34), "VREF_P",
                    ("DC", "dc=2.5"), value="2.5")
    labelled_source(sh, sim, VDC, "V4", G(64), G(34), "VREF_N",
                    ("DC", "dc=-2.5"), value="-2.5")
    labelled_source(sh, sim, VPULSE, "V5", G(88), G(34), "MCLK",
                    ("PULSE", f"y1=0 y2=5 td=0 tr=5n tf=5n "
                              f"tw={ns(T_MCLK / 2)} per={ns(T_MCLK)}"))
    note_block(sh, (G(120), G(20)),
               "The reference and MCLK are ideal sources here -- sim_b and\n"
               "sim_c are where they earn their numbers, and this run has to\n"
               "resolve a 1.536 MHz loop for 3 ms without also charging a\n"
               "440 uF reservoir.\n"
               "The NEGATIVE rail is not idealised, though: it is -3.87 V,\n"
               "which is what sim_a measured the charge pump actually making\n"
               "at 30 mA.  That is the rail the op-amps saturate against, and\n"
               "on this board saturation IS the clamp -- so idealising it to\n"
               "-5 V would hide the one thing this sheet exists to check.",
               size=1.27)

    # ---- the signal, and the click ---------------------------------------
    y = G(76)
    # -8 dBFS is the design's nominal operating point: 0.398 x 3.486 Vpk at
    # the wiper.  The front end's own divider (1R over 47k, behind the 1k of
    # the anti-alias filter) loses 2.1 % of it, hence 1.417 and not 1.387.
    v6 = sh.place(VSIN, "V6", at=(G(18), G(84)), value="1.417V 997Hz")
    sim["V6"] = src("SIN", "dc=0 ampl=1.417 f=997")
    v7 = sh.place(VPULSE, "V7", at=(G(18), G(100)), value="CLICK")
    sim["V7"] = src("PULSE", "y1=0 y2=10.68 td=1.5m tr=1u tf=1u "
                             "tw=40u per=10")
    sh.seg(v6.pin(2), v7.pin(1))
    sh.gnd(v7.pin(2), drop=STUB)
    sh.seg(v6.pin(1), (G(18), y))
    note_block(sh, (G(6), G(112)),
               "V6 is the signal at -8 dBFS, the design's nominal operating\n"
               "point.  V7 is the click, in series with it: 40 us at three\n"
               "times full scale, at t = 1.5 ms.\n"
               "A 1-bit third-order loop that overloads does not come back\n"
               "on its own, and on a vinyl source that is not a corner case.\n"
               "The op-amps' own saturation is the only rescue -- there are\n"
               "no clamp parts anywhere on this board.", size=1.27)

    # ---- the channel -----------------------------------------------------
    wiper = front_end(sh, G(30), y, r, "L", jack=False, pot=False)
    sh.seg((G(18), y), (G(30), y))

    X1, X2, X3, XI = G(94), G(158), G(222), G(286)
    i1 = summing_stage(sh, X1, y, [(None, r["Rin"], "20k5"),
                                   ("DACN_L", r["Rd1"], "14k7"),
                                   ("VREF_N", r["Ro1"], "14k7")],
                       "U40", 1, "C", r["C1"], "220p", opamp=OPA,
                       title="INTEGRATOR 1  (a1 = 0.247)")
    wpr = wiper.pin(2)
    sh.seg(wpr, (wpr.x + G(4), wpr.y))
    sh.seg((wpr.x + G(4), wpr.y), (wpr.x + G(4), y))
    sh.seg((wpr.x + G(4), y), (X1, y))
    sh.label((wpr.x + G(4), y), "WIPER", kind="global")

    i2 = summing_stage(sh, X2, y, [(None, r["R2"], "10k5"),
                                   ("DACP_L", r["Rd2"], "13k0"),
                                   ("VREF_N", r["Ro2"], "13k0"),
                                   (None, r["Rg"], "255k")],
                       "U41", 1, "C", r["C2"], "220p", opamp=OPA,
                       title="INTEGRATOR 2  (a2 = 0.321, + resonator)")
    board.elbow(sh, i1["out"], (X2, y), X2 - G(4))
    i3 = summing_stage(sh, X3, y, [(None, r["R3"], "5k90"),
                                   ("DACN_L", r["Rd3"], "8k25"),
                                   ("VREF_N", r["Ro3"], "8k25")],
                       "U42", 1, "C", r["C3"], "220p", opamp=OPA,
                       title="INTEGRATOR 3  (a3 = 0.611)")
    board.elbow(sh, i2["out"], (X3, y), X3 - G(4))
    inv = summing_stage(sh, XI, y, [(None, r["Ri"], "10k0")],
                        "U43", 1, "R", r["Rf"], "10k0", opamp=OPA,
                        title="RESONATOR INVERTER  (g = 0.0297)")
    board.elbow(sh, i3["out"], (XI, y), XI - G(4))
    for st in (i1, i2, i3, inv):
        sim[st["u"].ref] = dict(SIM_OPAMP)
        opamp_rails(sh, st["u"])
    for st, name in ((i1, "INT1"), (i2, "INT2"), (i3, "INT3")):
        sh.label((st["out"][0] - G(4), st["y_out"]), name, kind="global")
    sh.label((X1 + G(21), y + G(10)), "SUM1", kind="global")

    # resonator return, right to left along the bottom into integrator 2
    ret_y = y + G(52)
    ox, oy = inv["out"]
    sh.seg((ox, oy), (ox, ret_y))
    sh.seg((ox, ret_y), (X2 - G(2), ret_y))
    sh.seg((X2 - G(2), ret_y), (X2 - G(2), y + 3 * board.COL))
    sh.seg((X2 - G(2), y + 3 * board.COL), (X2, y + 3 * board.COL))

    # ---- quantiser, retiming and the DAC ---------------------------------
    XC = G(350)
    quantiser(sh, XC, y, r, "L", v3=i3)
    sim[r["Ucmp"]] = dict(SIM_LM311)

    ff = sh.place(DFF, "U30", at=(G(430), y + G(6)), value="74HC74")
    sim["U30"] = dict(SIM_DFF)
    d, ck = ff.pin("D"), ff.pin("C")
    sh.seg(d, (d.x - G(8), d.y))
    sh.label((d.x - G(8), d.y), "CMP_L", kind="global")
    sh.seg(ck, (ck.x - G(8), ck.y))
    sh.label((ck.x - G(8), ck.y), "MCLK", kind="global")
    for pn, lbl in (("Q", "QL"), ("~{Q}", "QNL")):
        p = ff.pin(pn)
        sh.seg(p, (p.x + G(8), p.y))
        sh.label((p.x + G(8), p.y), lbl, kind="global")
    for pn in ("~{S}", "~{R}"):
        p = ff.pin(pn)
        dy = -STUB if p.y < ff.y else STUB
        sh.seg(p, (p.x, p.y + dy))
        sh.rail((p.x, p.y + dy), net="+5V", rise=-dy if dy > 0 else STUB)
    sh.rail(ff.pin("VCC"), net="+5V", rise=STUB)
    sh.gnd(ff.pin("GND"), drop=STUB)

    for ref, dy, src_lbl, dst in (("U31", G(34), "QL", "DACN_L"),
                                  ("U32", G(58), "QNL", "DACP_L")):
        g = gate(sh, sim, ref, G(430), y + dy, SIM_HC04, "74HC04")
        sh.seg(g.pin("A"), (g.pin("A").x - G(6), g.pin("A").y))
        sh.label((g.pin("A").x - G(6), g.pin("A").y), src_lbl, kind="global")
        sh.seg(g.pin("Y"), (g.pin("Y").x + G(6), g.pin("Y").y))
        sh.label((g.pin("Y").x + G(6), g.pin("Y").y), dst, kind="global")
    note_block(sh, (G(404), y + G(72)),
               "DACN from Q and DACP from /Q, so the two DAC edges\n"
               "are as close to simultaneous as the parts allow", size=1.27)

    note_block(sh, (G(10), G(152)),
               "Three things to read off this sheet, in order of how much "
               "they matter.", size=1.6)
    note_block(sh, (G(10), G(158)),
               "1. THE CLICK TEST.  At 1.5 ms a 40 us transient at three "
               "times full scale hits the input.  The loop must come back:\n"
               "   the integrators must return to their normal 1.4-1.5 V "
               "swing and QL must go on toggling.  A modulator that latches\n"
               "   here is one that would need a power cycle after every "
               "click on the record.", size=1.27)
    note_block(sh, (G(10), G(170)),
               "2. WHERE THE TL074 ACTUALLY SATURATES.  There are no clamp "
               "parts: the integrator state scales are chosen so the\n"
               "   op-amps' own output saturation IS the clamp.  The design "
               "assumed about +/-2.7 V on +/-5 V rails.  If the real part\n"
               "   swings further, the clamp lands somewhere the Python model "
               "never simulated -- so measure it, do not assume it.",
               size=1.27)
    note_block(sh, (G(268), G(152)),
               "3. INTEGRATOR SWINGS AT -8 dBFS: 1.43 / 1.47 / 1.45 V, from "
               "docs/design-notes.md 3.  Bigger than that and the\n"
               "   overload margin has gone somewhere; smaller and the "
               "quantisation noise is being spent for nothing.", size=1.27)
    note_block(sh, (G(268), G(160)),
               "There is deliberately NO SNR figure here.  68 dB over a "
               "20 kHz band at OSR 32 needs about a second of transient at\n"
               "nanosecond steps; sim/verify.py computes it properly in "
               "minutes and this sheet would take hours to say the same.",
               size=1.27)
    cmd_note(sh, "sim_h_loop", (G(268), G(170)))
    return sim


# ===========================================================================
BACKLINK_Y = {"sim_a_pump": G(116), "sim_b_reference": G(106),
              "sim_c_clock": G(110), "sim_d_integrator": G(126),
              "sim_e_quantiser": G(136), "sim_f_dac": G(150),
              "sim_g_interface": G(144), "sim_h_loop": G(184)}


def main(wanted=None):
    write_sym_lib_table(SIM / "sym-lib-table",
                        {"vinyl_adc_sim":
                         "${KIPRJMOD}/lib/vinyl_adc_sim.kicad_sym"})
    bad = 0
    for name, title, uuid, paper, fn in BENCHES:
        if wanted and name not in wanted and name[4] not in wanted:
            continue
        sh = new_sheet(title, name, uuid, paper)
        sim = fn(sh)
        # passives last: a bench never overrides one deliberately
        for ref, fields in passive_sims(sh).items():
            sim.setdefault(ref, fields)
        problems = sh.check()
        for p in problems:
            print(f"  {name}: CHECK {p}")
            bad += 1
        links = back_link(sh, BACKLINK_Y.get(name, G(116)))
        out = SIM / f"{name}.kicad_sch"
        sh.emit(str(out))
        set_sim(out, sim)
        add_hrefs(out, links)
        board.write_project(str(out), uuid)
        write_workbook(SIM / f"{name}.wbk", *WORKBOOK[name])
        print(f"  {name:18s} {paper}  {len(sh.parts):3d} symbols, "
              f"{len(sh.wires):3d} wires, {len(sim)} models")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
