#!/usr/bin/env python3
"""Layout script for the discrete 3rd-order delta-sigma vinyl ADC.

Run:  py -3.13 vinyl_adc_layout.py  ->  ../vinyl_adc.kicad_sch

Component values come from sim/components.py, which derives them from the
loop coefficients and then re-simulates the snapped E96 values.  Do not
"tidy" a resistor here without re-running that script: the integrator state
scales are chosen so the op-amps saturate at the right level, and that
saturation is the only thing that stops a vinyl click latching the modulator.

Sheet plan (A2, four bands, signal left to right in each):
    A  y~36   power in, charge-pump -5 V, +/-2.5 V reference
    B  y~117  6.144 MHz clock, /4040 divider, quantiser flip-flops,
              interleave mux, DAC gates, level shift, Pi header
    C  y~203  channel L modulator
    D  y~273  channel R modulator
"""

import sys
import os

SKILL = r"C:\Users\Mads2\.claude\skills\kicad-schematic\scripts"
sys.path.insert(0, SKILL)

from schdraw import Sheet                     # noqa: E402
from simfields import add_hrefs               # noqa: E402

G = lambda n: round(n * 1.27, 2)              # noqa: E731

TL07X = "Amplifier_Operational:TL074"
TL072 = "Amplifier_Operational:TL072"
R_LIB, C_LIB = "Device:R", "Device:C"
CP_LIB = "Device:C_Polarized"

COL = G(8)           # 10.16  pitch of summing-input rows
FB = G(9)            # 11.43  op-amp centreline -> feedback row
STUB = G(4)          # 5.08

def new_sheet():
    return Sheet(paper="A2",
                 title="Discrete 3rd-order delta-sigma vinyl ADC  -  stereo, "
                       "48 kHz",
                 project="vinyl_adc")


# ---------------------------------------------------------------- helpers ---

def ic_supply(sh, part, vcc, gnd, cref, x_cap, rail="+5V"):
    """VCC up to a rail symbol, GND down to a GND symbol, 100n across."""
    vp, vn = part.pin(vcc), part.pin(gnd)
    ytop, ybot = vp.y - STUB, vn.y + STUB
    sh.seg(vp, (vp.x, ytop))
    sh.seg((vp.x, ytop), (x_cap, ytop))
    sh.rail((x_cap, ytop), net=rail, rise=STUB)
    sh.seg(vn, (vn.x, ybot))
    sh.seg((vn.x, ybot), (x_cap, ybot))
    c = sh.place(C_LIB, cref, at=(x_cap, round((ytop + ybot) / 2 / 1.27) * 1.27),
                 rot=0, value="100n")
    sh.seg((x_cap, ytop), c.pin(1))
    sh.seg(c.pin(2), (x_cap, ybot))
    sh.gnd((x_cap, ybot))


def note_block(sh, at, text, size=1.27):
    """Multi-line annotation, one note_block() per line.

    schdraw writes note text into the s-expression verbatim, so a string with
    an embedded newline produces a raw newline inside a quoted token and KiCad
    10 refuses to load the whole file -- while sch_score and the in-process
    checks all still pass.  Splitting the lines here side-steps it.
    """
    x, y = at
    step = 1.27 * max(2, round(size * 1.6 / 1.27))
    for i, line in enumerate(str(text).splitlines() or [""]):
        sh.note((x, y + i * step), line, size=size)


def gate_pins(part, at_x):
    """(left pins, right pins) of a gate unit, top to bottom.

    Unit pin ORDER is not consistent across a package -- 74HC04 unit 4 lists
    its output first -- so pick inputs and outputs by which side of the symbol
    they sit on rather than by index.
    """
    left = sorted([q for q in part.pins if q.x < at_x], key=lambda q: q.y)
    right = sorted([q for q in part.pins if q.x > at_x], key=lambda q: q.y)
    return left, right


def tie_low(sh, *pins):
    """Unused CMOS inputs must not float: one shared bus, one GND symbol.

    Giving each pin its own downward GND drop looks tidier and is WRONG: on a
    2.54 mm pin pitch a 5.08 mm drop ends exactly on the next pin's stub, so
    KiCad puts a junction there and the two pins short.  That is how the whole
    74HC157 ended up on one net.""" 
    ps = sorted(pins, key=lambda q: q.y)
    x = min(q.x for q in ps) - STUB
    for q in ps:
        sh.seg(q, (x, q.y))
    if len(ps) > 1:
        sh.seg((x, ps[0].y), (x, ps[-1].y))
    # drop=0: the symbol hangs straight off the end of the bus.  A 5.08 drop
    # here is what shorted MCLK to ground -- it landed exactly on the mux's
    # select-pin stub one row below.
    sh.gnd((x, ps[-1].y), drop=0)


def summing_stage(sh, x, y0, rows, uref, unit, fb_kind, fb_ref, fb_val,
                      opamp=TL07X, title=None, title_dy=G(-20)):
    """One inverting stage: N summing inputs -> virtual earth -> op-amp.

    `rows` is a list of (global_label_or_None, refdes, value); a None label
    means that row is the block's signal input port, wired by the caller.
    `fb_kind` is "C" for an integrator or "R" for a plain inverter.

    Returns dict with in/out ports and the resistor parts.
    """
    n = len(rows)
    y_s = y0 + (n - 1) * COL / 2.0
    y_s = round(y_s / 1.27) * 1.27
    y_bot = y0 + (n - 1) * COL
    y_fb = max(y_s + FB, y_bot + G(8))
    bus_x = x + G(21)                      # 26.67

    u = sh.place(opamp, uref, at=(x + G(38), y_s - G(2)), unit=unit,
                 value=opamp.split(":")[1])
    plus, minus, out = u.pin("+"), u.pin("-"), u.pin("out")

    parts = {}
    for i, (lbl, rref, rval) in enumerate(rows):
        ry = y0 + i * COL
        r = sh.place(R_LIB, rref, at=(x + G(12), ry), rot=90, value=rval)
        sh.seg((x, ry), r.pin(1))
        sh.seg(r.pin(2), (bus_x, ry))
        if lbl:
            sh.label((x, ry), lbl, kind="global")
        parts[rref] = r

    sh.seg((bus_x, y0), (bus_x, y_bot))                    # the summing bus
    sh.seg((bus_x, y_s), minus)

    lib = C_LIB if fb_kind == "C" else R_LIB
    fb = sh.place(lib, fb_ref, at=(x + G(38), y_fb), rot=90, value=fb_val)
    sh.seg((x + G(29), y_s), (x + G(29), y_fb))            # tap down
    sh.seg((x + G(29), y_fb), fb.pin(1))
    sh.seg(fb.pin(2), (x + G(46), y_fb))
    sh.seg((x + G(46), y_fb), (x + G(46), y_s - G(2)))
    sh.seg(out, (x + G(52), y_s - G(2)))                   # output run

    # `+` to ground: leaves left and descends, crossing the bus->`-` lead
    sh.seg(plus, (x + G(25), y_s - G(4)))
    sh.seg((x + G(25), y_s - G(4)), (x + G(25), y_fb + G(8)))
    sh.gnd((x + G(25), y_fb + G(8)))

    if title:
        note_block(sh, (x, y0 + title_dy), title, size=2.0)

    return {"in": (x, y0), "out": (x + G(52), y_s - G(2)),
            "y_out": y_s - G(2), "parts": parts, "u": u, "y_fb": y_fb}


def elbow(sh, a, b, xmid):
    """Route a -> b as horizontal, vertical, horizontal through xmid."""
    ax, ay = a
    bx, by = b
    sh.seg((ax, ay), (xmid, ay))
    sh.seg((xmid, ay), (xmid, by))
    sh.seg((xmid, by), (bx, by))


# The SPICE testbenches in sim/, as a clickable index.
#
# Hyperlinks, not hierarchical sheets.  Attaching a bench as a sheet of this
# project was measured on another board and it is wrong three ways: the
# bench's supply welds onto the board's real rail because power symbols are
# global across a hierarchy, its sources land in the board netlist ready for
# Update PCB from Schematic to put them on copper, and any refdes it shares
# with the board silently merges with it.  A hierarchy is one electrical
# design; these are eight separate ones.
#
# The href needs a scheme.  A bare relative path, or a bare ${KIPRJMOD}/...,
# is rejected when the file loads -- so the schematic reads as CORRUPT rather
# than as a broken link.  "file:sim/x.kicad_sch" carries a scheme and stays
# relative, so it survives the repository being cloned anywhere.  It points
# at the .kicad_sch and not the .kicad_pro because the OS opens a project
# file with the project manager, one click short of the drawing.
SIM_LINKS = [
    ("SPICE TESTBENCHES  (sim/, one project each -- click to open)", None),
    ("A  rails and the -5 V charge pump", "sim_a_pump"),
    ("B  the +/-2.5 V ratiometric reference", "sim_b_reference"),
    ("C  clock buffer and 74HC4040 divider", "sim_c_clock"),
    ("D  integrator 1 with a real TL074", "sim_d_integrator"),
    ("E  LM311 quantiser on a single supply", "sim_e_quantiser"),
    ("F  the 1-bit DAC and its offset leg", "sim_f_dac"),
    ("G  retiming, interleave and the 3.3 V level shift", "sim_g_interface"),
    ("H  one complete channel, with the click test", "sim_h_loop"),
]


def sim_index(sh, x, y):
    """Draw the testbench index and return {text: href} for add_hrefs()."""
    links = {}
    for i, (text, name) in enumerate(SIM_LINKS):
        sh.note((x, y + i * G(4)), text, size=1.6 if name else 1.8)
        if name:
            links[text] = f"file:sim/{name}.kicad_sch"
    return links


# =============================================================== BAND A: POWER

def charge_pump(sh, px, y):
    """The -5 V rail: a 74HC244 with all eight buffers paralleled, two
    Schottkys and an RC post-filter.

    There is no charge-pump IC in the DTU shop, so the driver is eight bus
    buffers in parallel -- about 32 mA, which is the whole analog budget and
    the reason the comparators run single-supply (docs/design-notes.md 6).

    D1 returns the pump node to ground on the driver's HIGH half, so its
    ANODE faces the pump node; D2 hands the negative excursion to the
    reservoir on the LOW half, so its CATHODE faces the pump node.  Reverse
    either and the circuit is a voltage doubler making about +4.5 V, which is
    what sim_a_pump exists to catch -- it was drawn that way, and every other
    gate in this toolkit passed it.
    """
    u1 = sh.place("74xx:74HC244", "U1", at=(px, y + G(12)), value="74HC244")
    ins = [u1.pin(n) for n in (2, 4, 6, 8, 17, 15, 13, 11)]
    outs = [u1.pin(n) for n in (18, 16, 14, 12, 3, 5, 7, 9)]
    xin = ins[0].x - G(6)
    for p in ins:
        sh.seg(p, (xin, p.y))
    sh.seg((xin, ins[0].y), (xin, ins[-1].y))
    sh.seg((xin, ins[0].y), (xin - G(6), ins[0].y))
    sh.label((xin - G(6), ins[0].y), "PUMP", kind="global")
    xout = outs[0].x + G(6)
    for p in outs:
        sh.seg(p, (xout, p.y))
    sh.seg((xout, outs[0].y), (xout, outs[-1].y))
    tie_low(sh, u1.pin(1), u1.pin(19))                         # both /OE low
    ic_supply(sh, u1, 20, 10, "C3", px + G(24))
    note_block(sh, (px - G(14), y - G(6)),
            "8 buffers paralleled ~= 32 mA;\nno charge-pump IC in the shop",
            size=1.27)

    # pump capacitor, rectifier, reservoir
    cy = outs[0].y
    c4 = sh.place(CP_LIB, "C4", at=(xout + G(8), cy), rot=90, value="10u")
    sh.seg((xout, cy), c4.pin(1))
    nx = c4.pin(2).x + G(6)
    sh.seg(c4.pin(2), (nx, cy))
    # D1 returns the pump node to ground on the driver's HIGH half, so its
    # ANODE faces the pump node; D2 hands the negative excursion to the
    # reservoir on the LOW half, so its CATHODE faces the pump node.
    #
    # Device:D_Schottky numbers pin 1 = K and pin 2 = A -- cathode first, which
    # is the opposite of the reading that seems natural -- and at rot=90 pin 1
    # lands at the BOTTOM.  Both diodes were drawn that way round, which makes
    # this a positive voltage doubler: sim/sim_a_pump measured +3.4 V on the
    # net called -5V.  Nothing else caught it.  sch_score, ERC, the netlist
    # read-back and check_intent.py all passed on the reversed version,
    # because a diode connected the wrong way round is still connected.
    d1 = sh.place("Device:D_Schottky", "D1", at=(nx, cy - G(8)), rot=270,
                  value="1N5817")
    sh.seg((nx, cy), d1.pin(2))
    sh.seg(d1.pin(1), (nx, cy - G(14)))
    sh.gnd((nx, cy - G(14)), drop=0)
    d2 = sh.place("Device:D_Schottky", "D2", at=(nx, cy + G(8)), rot=270,
                  value="1N5817")
    sh.seg((nx, cy), d2.pin(1))
    sh.seg(d2.pin(2), (nx, cy + G(14)))
    ry = cy + G(14)
    c5 = sh.place(CP_LIB, "C5", at=(nx + G(10), ry + G(6)), rot=180,
                  value="220u")
    sh.seg((nx, ry), (nx + G(10), ry))
    sh.seg((nx + G(10), ry), c5.pin(2))
    sh.seg(c5.pin(1), (nx + G(10), ry + G(12)))
    sh.gnd((nx + G(10), ry + G(12)))
    r1 = sh.place(R_LIB, "R1", at=(nx + G(18), ry), rot=90, value="4R75")
    sh.seg((nx + G(10), ry), r1.pin(1))
    c6 = sh.place(CP_LIB, "C6", at=(nx + G(26), ry + G(6)), rot=180,
                  value="220u")
    sh.seg(r1.pin(2), (nx + G(26), ry))
    sh.seg((nx + G(26), ry), c6.pin(2))
    sh.seg(c6.pin(1), (nx + G(26), ry + G(12)))
    sh.gnd((nx + G(26), ry + G(12)))
    sh.seg((nx + G(26), ry), (nx + G(30), ry))
    sh.rail((nx + G(30), ry), net="-5V", rise=-STUB)
    note_block(sh, (nx - G(4), ry + G(19)),
            "192 kHz pump drive = 4x the 48 kHz output rate,\n"
            "so residual ripple lands on a CIC decimator null.", size=1.27)
    return {"node": (nx, cy), "out": (nx + G(30), ry), "u": u1}


def reference(sh, rx, y, opamp=TL072, refs=("U2", "U2"), supply=True):
    """The +/-2.5 V DAC reference, ratiometric off the same +5 V rail.

    Deliberately NOT filtered: because the divider tracks the rail the gate
    runs on, rail noise appears as a common-mode gain modulation at -98 dB
    instead of as additive noise, and filtering the reference would break
    that cancellation (docs/design-notes.md 6).

    `refs`/`supply` exist for the testbench: KiCad's SPICE exporter has no
    notion of symbol units, so a bench needs one refdes and one single-unit
    symbol per section, and it wires the rails itself instead of hanging a
    package supply unit off the pair.

    Returns the two op-amp sections.
    """
    note_block(sh, (rx - G(8), y - G(16)),
            "REFERENCE  (+/-2.5V, ratiometric -- tracks +5V so rail noise "
            "cancels as gain, not additive noise)", size=2.0)
    r2 = sh.place(R_LIB, "R2", at=(rx, y + G(2)), rot=0, value="10k0")
    r3 = sh.place(R_LIB, "R3", at=(rx, y + G(12)), rot=0, value="10k0")
    sh.seg(r2.pin(1), (rx, y - G(2)))
    sh.rail((rx, y - G(2)), net="+5V", rise=STUB)
    sh.seg(r2.pin(2), r3.pin(1))
    sh.seg(r3.pin(2), (rx, y + G(18)))
    sh.gnd((rx, y + G(18)))
    mid = r2.pin(2).y + (r3.pin(1).y - r2.pin(2).y) / 2
    mid = round(mid / 1.27) * 1.27

    u2a = sh.place(opamp, refs[0], at=(rx + G(16), mid + G(2)),
                   unit=1, value=opamp.split(":")[1])
    sh.seg((rx, mid), (u2a.pin("+").x, mid))
    sh.seg(u2a.pin("out"), (u2a.pin("out").x + G(4), mid + G(2)))
    fbx = u2a.pin("out").x + G(4)
    sh.seg((fbx, mid + G(2)), (fbx, mid + G(10)))
    sh.seg((fbx, mid + G(10)), (u2a.pin("-").x - G(3), mid + G(10)))
    sh.seg((u2a.pin("-").x - G(3), mid + G(10)),
           (u2a.pin("-").x - G(3), u2a.pin("-").y))
    sh.seg((u2a.pin("-").x - G(3), u2a.pin("-").y), u2a.pin("-"))
    sh.seg((fbx, mid + G(2)), (fbx + G(6), mid + G(2)))
    sh.label((fbx + G(6), mid + G(2)), "VREF_P", kind="global")

    # inverter: VREF_P -> -2.5 V
    ix = fbx + G(14)
    iy = mid + G(24)
    r4 = sh.place(R_LIB, "R4", at=(ix + G(12), iy), rot=90, value="10k0")
    sh.seg((ix, iy), r4.pin(1))
    sh.label((ix, iy), "VREF_P", kind="global")
    u2b = sh.place(opamp, refs[1], at=(ix + G(38), iy - G(2)),
                   unit=1 if refs[0] != refs[1] else 2,
                   value=opamp.split(":")[1])
    sh.seg(r4.pin(2), (ix + G(21), iy))
    sh.seg((ix + G(21), iy), u2b.pin("-"))
    r5 = sh.place(R_LIB, "R5", at=(ix + G(38), iy + FB), rot=90, value="10k0")
    sh.seg((ix + G(29), iy), (ix + G(29), iy + FB))
    sh.seg((ix + G(29), iy + FB), r5.pin(1))
    sh.seg(r5.pin(2), (ix + G(46), iy + FB))
    sh.seg((ix + G(46), iy + FB), (ix + G(46), iy - G(2)))
    sh.seg(u2b.pin("out"), (ix + G(52), iy - G(2)))
    sh.label((ix + G(52), iy - G(2)), "VREF_N", kind="global")
    sh.seg(u2b.pin("+"), (ix + G(25), iy - G(4)))
    sh.seg((ix + G(25), iy - G(4)), (ix + G(25), iy + G(16)))
    sh.gnd((ix + G(25), iy + G(16)))

    if not supply:
        return u2a, u2b

    sup = sh.place(TL072, "U2", at=(rx + G(16), mid + G(30)), unit=3,
                  value="TL072")
    vp, vn = sup.pin("V+"), sup.pin("V-")
    sh.seg(vp, (vp.x, vp.y - STUB))
    sh.rail((vp.x, vp.y - STUB), net="+5V", rise=STUB)
    sh.seg(vn, (vn.x, vn.y + STUB))
    sh.rail((vn.x, vn.y + STUB), net="-5V", rise=-STUB)
    c7 = sh.place(C_LIB, "C7", at=(vp.x + G(10), vp.y - STUB + G(3)), rot=0,
                  value="100n")
    sh.seg((vp.x, vp.y - STUB), (vp.x + G(10), vp.y - STUB))
    sh.seg((vp.x + G(10), vp.y - STUB), c7.pin(1))
    c8 = sh.place(C_LIB, "C8", at=(vp.x + G(10), vn.y + STUB - G(3)), rot=0,
                  value="100n")
    sh.seg(c7.pin(2), c8.pin(1))
    sh.seg(c8.pin(2), (vp.x + G(10), vn.y + STUB))
    sh.seg((vn.x, vn.y + STUB), (vp.x + G(10), vn.y + STUB))
    gy = round((c7.pin(2).y + c8.pin(1).y) / 2 / 1.27) * 1.27
    sh.seg((vp.x + G(10), gy), (vp.x + G(16), gy))
    sh.power("power:GND", (vp.x + G(16), gy), rot=270)
    return u2a, u2b



def band_power(sh, y):
    note_block(sh, (G(16), y - G(16)), "POWER  (Pi +5V -> charge-pump -5V -> "
            "+/-2.5V DAC reference)", size=2.0)

    # -- incoming +5 V, bulk decoupling, and the flags -----------------------
    x = G(20)
    sh.rail((x, y), net="+5V", rise=STUB)
    sh.seg((x, y), (x, y + G(6)))
    c1 = sh.place(CP_LIB, "C1", at=(x, y + G(10)), rot=0, value="470u")
    sh.seg((x, y + G(6)), c1.pin(1))
    c2 = sh.place(C_LIB, "C2", at=(x + G(8), y + G(10)), rot=0, value="100n")
    sh.seg((x, y + G(6)), (x + G(8), y + G(6)))
    sh.seg((x + G(8), y + G(6)), c2.pin(1))
    sh.seg(c1.pin(2), (x, y + G(14)))
    sh.seg(c2.pin(2), (x + G(8), y + G(14)))
    sh.seg((x, y + G(14)), (x + G(8), y + G(14)))
    sh.gnd((x + G(4), y + G(14)))
    note_block(sh, (x - G(4), y + G(19)),
            "Reservoir sits AT the DAC gate: the DAC's mean supply current\n"
            "is proportional to the signal, so this rail must be LOW\n"
            "IMPEDANCE, not filtered by a series R.", size=1.27)

    # PWR_FLAGs, in their own row
    for i, (net, lib) in enumerate((("+5V", "power:+5V"), ("-5V", "power:-5V"),
                                    ("+3V3", "power:+3V3"), ("GND", "power:GND"))):
        fx = G(20) + i * G(12)
        fy = y - G(10)
        sh.power(lib, (fx, fy), rot=0 if net != "GND" else 0)
        sh.seg((fx, fy), (fx, fy + G(3)))
        sh.power("power:PWR_FLAG", (fx, fy + G(3)), rot=180)

    # -- charge pump: 74HC244, all eight buffers in parallel -------------
    charge_pump(sh, G(75), y)

    # -- +/-2.5 V reference, ratiometric off the same +5 V rail --------
    reference(sh, G(250), y)

# ============================================================ BAND B: DIGITAL

def clock_divider(sh, dx, y, clk_label="CLK6M", out_labels=True,
                  nc_spares=True, cap_x=None):
    """The 74HC4040 that makes every clock on the board from one 6.144 MHz can.

    Q0 = BCLK 3.072 MHz, Q1 = MCLK 1.536 MHz, Q4 = the 192 kHz charge-pump
    drive and Q6 = LRCLK 48 kHz -- pins 9, 7, 3 and 4, worth stating in pin
    numbers because the divide-by-two stage being called Q0 rather than Q1 is
    an easy off-by-one to wire.

    Everything downstream of it changes on a master-clock falling edge, which
    is what gives the Pi its I2S setup margin; sim_c_clock measures how much
    of that the ripple delay eats.

    The three switches exist for the testbenches, which wire the clock in and
    the outputs onward rather than naming them -- on a bench sheet a source
    sitting next to the pin it drives is a wire, not a long haul, and the
    scorer is right to say so.  Returns the counter, its clock pin, the four
    used output pins by name and the spare output pins.
    """
    u4 = sh.place("4xxx:4040", "U4", at=(dx, y + G(10)), value="74HC4040")
    if clk_label:
        sh.seg(u4.pin(10), (u4.pin(10).x - G(6), u4.pin(10).y))
        sh.label((u4.pin(10).x - G(6), u4.pin(10).y), clk_label, kind="global")
    tie_low(sh, u4.pin(11))                                    # Reset held low
    outs = {}
    for pin, lbl in ((9, "BCLK"), (7, "MCLK"), (3, "PUMP"), (4, "LRCLK")):
        p = u4.pin(pin)
        outs[lbl] = p
        if out_labels:
            sh.seg(p, (p.x + G(8), p.y))
            sh.label((p.x + G(8), p.y), lbl, kind="global")
    spares = [u4.pin(pin) for pin in (6, 5, 2, 13, 12, 14, 15, 1)]
    if nc_spares:
        for p in spares:
            sh.nc(p)
    # cap_x moves the decoupling column: a testbench that runs the twelve
    # outputs off to the right needs it out of their way, because two wires
    # crossing get a junction and become one net
    ic_supply(sh, u4, 16, 8, "C11", dx + G(24) if cap_x is None else cap_x)
    note_block(sh, (dx - G(14), y - G(6)),
            "Q0=BCLK 3.072M  Q1=MCLK 1.536M\nQ4=PUMP 192k  Q6=LRCLK 48k",
            size=1.27)
    return {"u": u4, "clk": u4.pin(10), "outs": outs, "spares": spares}



def band_digital(sh, y):
    note_block(sh, (G(16), y - G(16)),
            "CLOCK AND DIGITAL  (6.144 MHz -> /2 BCLK 3.072M, /4 MCLK 1.536M, "
            "/128 LRCLK 48k;  L and R interleaved onto one DIN)", size=2.0)

    # -- oscillator and source-select jumper --------------------------------
    ox = G(18)
    x1 = sh.place("Oscillator:CXO_DIP8", "X1", at=(ox, y + G(8)),
                  value="6.144MHz")
    sh.seg(x1.pin(1), (x1.pin(1).x - STUB, x1.pin(1).y))
    sh.rail((x1.pin(1).x - STUB, x1.pin(1).y), net="+5V", rise=STUB)
    sh.seg(x1.pin(8), (x1.pin(8).x, x1.pin(8).y - STUB))
    sh.rail((x1.pin(8).x, x1.pin(8).y - STUB), net="+5V", rise=STUB)
    sh.seg(x1.pin(4), (x1.pin(4).x, x1.pin(4).y + STUB))
    sh.gnd((x1.pin(4).x, x1.pin(4).y + STUB))
    c9 = sh.place(C_LIB, "C9", at=(ox + G(12), y + G(8)), rot=0, value="100n")
    sh.seg(x1.pin(8), (ox + G(12), x1.pin(8).y))
    sh.seg((ox + G(12), x1.pin(8).y), c9.pin(1))
    sh.seg(c9.pin(2), (ox + G(12), x1.pin(4).y))
    sh.seg(x1.pin(4), (ox + G(12), x1.pin(4).y))

    # J1 sits below the can so the oscillator's output run clears its pins,
    # and every approach is horizontal: a vertical down a header's pin column
    # shorts every pin it passes.
    j1 = sh.place("Connector_Generic:Conn_01x03", "J1",
                  at=(ox + G(30), y + G(16)), mirror="y", value="CLK SEL")
    far = j1.pin(1).x + G(10)
    sh.seg(x1.pin(5), (far, x1.pin(5).y))
    sh.seg((far, x1.pin(5).y), (far, j1.pin(1).y))
    sh.seg((far, j1.pin(1).y), j1.pin(1))
    sh.seg(j1.pin(3), (j1.pin(3).x + G(2), j1.pin(3).y))
    sh.label((j1.pin(3).x + G(2), j1.pin(3).y), "GPCLK0", kind="global")
    sh.seg(j1.pin(2), (j1.pin(2).x + G(5), j1.pin(2).y))
    sh.seg((j1.pin(2).x + G(5), j1.pin(2).y), (j1.pin(2).x + G(5), y + G(24)))
    note_block(sh, (ox - G(2), y + G(30)),
            "Jumper 1-2 = on-board can (crystal jitter 20 ps -> 102 dB floor).\n"
            "Jumper 2-3 = Pi GPCLK0 fallback: ~1 ns jitter -> 68 dB floor,\n"
            "which would become the dominant noise source.  Bring-up only.",
            size=1.27)

    # -- 74HCT132 clock buffer (HCT so a 3.3 V source still meets VIH) -------
    bx = ox + G(56)   # far enough right that the buffer's input riser
                      # clears every stub on the clock-select jumper
    u3 = sh.place("74xx:74LS132", "U3", at=(bx, y + G(8)), unit=1,
                  value="74HCT132")
    sh.seg((j1.pin(2).x + G(5), y + G(24)), (u3.pin(1).x - G(4), y + G(24)))
    sh.seg((u3.pin(1).x - G(4), y + G(24)), (u3.pin(1).x - G(4), u3.pin(1).y))
    sh.seg((u3.pin(1).x - G(4), u3.pin(1).y), u3.pin(1))
    sh.seg((u3.pin(1).x - G(4), u3.pin(1).y), (u3.pin(1).x - G(4), u3.pin(2).y))
    sh.seg((u3.pin(1).x - G(4), u3.pin(2).y), u3.pin(2))
    sh.seg(u3.pin(3), (u3.pin(3).x + G(6), u3.pin(3).y))
    sh.label((u3.pin(3).x + G(6), u3.pin(3).y), "CLK6M", kind="global")
    # spare gates get one compact strip rather than a tall stacked column
    for i, un in enumerate((2, 3, 4)):
        gx_ = bx + G(0) + i * G(18)
        g = sh.place("74xx:74LS132", "U3", at=(gx_, y + G(40)),
                     unit=un, value="74HCT132")
        li, ri = gate_pins(g, gx_)
        tie_low(sh, *li)
        sh.nc(*ri)
    note_block(sh, (bx - G(4), y + G(50)), "spare gates: inputs tied low", size=1.27)
    u3p = sh.place("74xx:74LS132", "U3", at=(bx + G(20), y + G(8)), unit=5,
                   value="74HCT132")
    ic_supply(sh, u3p, 14, 7, "C10", u3p.pin(14).x + G(10))

    # -- 74HC4040 divider ----------------------------------------------------
    clock_divider(sh, G(126), y)

    # -- 74HC74 quantiser flip-flops (one section per channel) --------------
    fx = G(184)
    for i, ch in enumerate(("L", "R")):
        ff = sh.place("74xx:74HC74", "U5", at=(fx, y + G(6) + i * G(30)),
                      unit=i + 1, value="74HC74")
        d, ck = ff.pin("D"), ff.pin("C")
        sh.seg(d, (d.x - G(6), d.y))
        sh.label((d.x - G(6), d.y), f"CMP_{ch}", kind="global")
        sh.seg(ck, (ck.x - G(6), ck.y))
        sh.label((ck.x - G(6), ck.y), "MCLK", kind="global")
        q, qn = ff.pin("Q"), ff.pin("~{Q}")
        sh.seg(q, (q.x + G(6), q.y))
        sh.label((q.x + G(6), q.y), f"Q{ch}", kind="global")
        sh.seg(qn, (qn.x + G(6), qn.y))
        sh.label((qn.x + G(6), qn.y), f"QN{ch}", kind="global")
        for pn in ("~{R}", "~{S}"):
            p = ff.pin(pn)
            dy = STUB if p.y > ff.pin("D").y else -STUB
            sh.seg(p, (p.x, p.y + dy))
            sh.seg((p.x, p.y + dy), (p.x + G(5), p.y + dy))
            sh.rail((p.x + G(5), p.y + dy), net="+5V",
                    rise=STUB if dy < 0 else -STUB)
    u5p = sh.place("74xx:74HC74", "U5", at=(fx + G(22), y + G(6)), unit=3,
                   value="74HC74")
    ic_supply(sh, u5p, 14, 7, "C12", u5p.pin(14).x + G(10))

    # -- 74HC157 interleave mux ---------------------------------------------
    mx = G(238)
    u6 = sh.place("74xx:74LS157", "U6", at=(mx, y + G(14)), value="74HC157")
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
    ic_supply(sh, u6, 16, 8, "C13", mx + G(24))
    note_block(sh, (mx - G(16), y - G(6)),
            "MCLK selects: DIN carries R,L,R,L... at 3.072 Mbps.\n"
            "64 BCLK per LRCLK frame = 32 L bits + 32 R bits\n"
            "= exactly one OSR-32 sample per channel.", size=1.27)

    # -- 74HC04 DAC drive gates ---------------------------------------------
    gx = G(300)
    note_block(sh, (gx - G(10), y - G(6)),
            "1-BIT DAC DRIVE\nDACN = /Q, DACP = Q (taken from Q and /Q so the\n"
            "two edges are as close to simultaneous as the parts allow)",
            size=1.27)
    for i, (src, dst) in enumerate((("QL", "DACN_L"), ("QNL", "DACP_L"),
                                    ("QR", "DACN_R"), ("QNR", "DACP_R"))):
        g = sh.place("74xx:74HC04", "U7", at=(gx, y + G(6) + i * G(10)),
                     unit=i + 1, value="74HC04")
        li, ri = gate_pins(g, gx)
        ip, op = li[0], ri[0]
        sh.seg(ip, (ip.x - G(6), ip.y))
        sh.label((ip.x - G(6), ip.y), src, kind="global")
        sh.seg(op, (op.x + G(6), op.y))
        sh.label((op.x + G(6), op.y), dst, kind="global")
    for i, un in enumerate((5, 6)):
        g = sh.place("74xx:74HC04", "U7", at=(gx + i * G(24), y + G(46)),
                     unit=un, value="74HC04")
        li, ri = gate_pins(g, gx + i * G(24))
        tie_low(sh, *li)
        sh.nc(*ri)
    u7p = sh.place("74xx:74HC04", "U7", at=(gx + G(22), y + G(6)), unit=7,
                   value="74HC04")
    ic_supply(sh, u7p, 14, 7, "C14", u7p.pin(14).x + G(10))

    # -- 74HC4049 level shift 5 V -> 3.3 V, two stages per signal -----------
    lx = G(352)
    note_block(sh, (lx - G(8), y - G(6)),
            "LEVEL SHIFT to 3.3 V.  74HC4049 tolerates inputs above its own\n"
            "VCC, which is exactly what makes it legal here.  Two inverters\n"
            "per signal so BCLK polarity is preserved -- inverting BCLK would\n"
            "make the Pi sample on the data transition.", size=1.27)
    for i, sig in enumerate(("BCLK", "LRCLK", "DIN")):
        a = sh.place("4xxx:4049", "U8", at=(lx, y + G(6) + i * G(14)),
                     unit=2 * i + 1, value="74HC4049")
        b = sh.place("4xxx:4049", "U8", at=(lx + G(16), y + G(6) + i * G(14)),
                     unit=2 * i + 2, value="74HC4049")
        la, ra = gate_pins(a, lx)
        lb, rb_ = gate_pins(b, lx + G(16))
        ai, ao = la[0], ra[0]
        bi, bo = lb[0], rb_[0]
        sh.seg(ai, (ai.x - G(6), ai.y))
        sh.label((ai.x - G(6), ai.y), sig, kind="global")
        sh.seg(ao, bi)
        sh.seg(bo, (bo.x + G(6), bo.y))
        sh.label((bo.x + G(6), bo.y), f"PI_{sig}", kind="global")
    u8p = sh.place("4xxx:4049", "U8", at=(lx + G(34), y + G(6)), unit=7,
                   value="74HC4049")
    ic_supply(sh, u8p, 1, 8, "C15", u8p.pin(1).x + G(10), rail="+3V3")

    # -- Pi header -----------------------------------------------------------
    hx = G(424)
    j2 = sh.place("Connector_Generic:Conn_01x08", "J2", at=(hx, y + G(14)),
                  mirror="y", value="TO PI GPIO")
    rows = [(1, "+5V", "rail"), (2, "GND", "gnd"), (3, "+3V3", "rail"),
            (4, "PI_BCLK", "lbl"), (5, "PI_LRCLK", "lbl"),
            (6, "PI_DIN", "lbl"), (7, "GPCLK0", "lbl"), (8, "GND", "gnd")]
    # Every stub ends in its symbol or label with NO vertical: on a 2.54 mm
    # pin pitch any riser lands on a neighbour's stub.  The two grounds are the
    # one exception and get a shared bus, run further out than every other stub
    # so it crosses nothing.
    gnd_x = j2.pin(1).x - G(15)
    gnds = [j2.pin(pin) for pin, n, k in rows if k == "gnd"]
    for p in gnds:
        sh.seg(p, (gnd_x, p.y))
    sh.seg((gnd_x, gnds[0].y), (gnd_x, gnds[-1].y))
    sh.gnd((gnd_x, gnds[-1].y), drop=STUB)
    for pin, name, kind in rows:
        if kind == "gnd":
            continue
        p = j2.pin(pin)
        tx = p.x - G(8)
        sh.seg(p, (tx, p.y))
        if kind == "lbl":
            sh.label((tx, p.y), name, kind="global")
        else:
            sh.rail((tx, p.y), net=name, rise=0)
    note_block(sh, (hx - G(12), y + G(32)),
            "Pi pins: 1=+5V(pin2)  2=GND(6)  3=+3V3(1)\n"
            "4=BCLK GPIO18(12)  5=LRCLK GPIO19(35)\n"
            "6=DIN GPIO20(38)   7=GPCLK0 GPIO4(7)  8=GND(39)\n"
            "Pi is I2S SLAVE: this board is the clock master.", size=1.27)


# ====================================================== BANDS C/D: MODULATORS

def front_end(sh, jx, y, r, ch, jack=True, pot=True):
    """Line input: DC block, anti-alias RC and the level trimmer.

    `jack=False` leaves the connector off so a testbench can drive the same
    network from a source.  `pot=False` draws the trimmer as its two halves at
    FULL rotation, which is the setting every number in docs/design-notes.md
    assumes -- and, unlike a potentiometer symbol, something a SPICE deck can
    actually solve, because no one ships a model for a three-terminal pot.

    Returns the part whose pin 2 is the wiper.
    """
    cin = sh.place(C_LIB, r["Cin"], at=(jx + G(12), y), rot=90, value="2u2")
    if not jack:
        # no connector: the caller drives (jx, y) instead
        sh.seg((jx, y), cin.pin(1))
    if jack:
        j = sh.place("Connector:Screw_Terminal_01x02", r["J"], at=(jx, y),
                     mirror="y", value=f"LINE IN {ch}")
        sh.seg(j.pin(1), cin.pin(1))
        sh.seg(j.pin(2), (j.pin(2).x + G(3), j.pin(2).y))
        sh.seg((j.pin(2).x + G(3), j.pin(2).y),
               (j.pin(2).x + G(3), y + G(10)))
        sh.gnd((j.pin(2).x + G(3), y + G(10)))

    raa = sh.place(R_LIB, r["Raa"], at=(jx + G(24), y), rot=90, value="1k00")
    sh.seg(cin.pin(2), raa.pin(1))
    caa = sh.place(C_LIB, r["Caa"], at=(jx + G(32), y + G(6)), rot=0,
                   value="1n5")
    sh.seg(raa.pin(2), (jx + G(32), y))
    sh.seg((jx + G(32), y), caa.pin(1))
    sh.seg(caa.pin(2), (jx + G(32), y + G(12)))
    sh.gnd((jx + G(32), y + G(12)))

    if pot:
        rv = sh.place("Device:R_Potentiometer_Trim", r["RV"],
                      at=(jx + G(42), y + G(3)), value="47k")
        sh.seg((jx + G(32), y), (rv.pin(1).x, y))
        sh.seg((rv.pin(1).x, y), rv.pin(1))
        sh.seg(rv.pin(3), (rv.pin(3).x, y + G(12)))
        sh.gnd((rv.pin(3).x, y + G(12)))
    else:
        rv = sh.place(R_LIB, r["RV"], at=(jx + G(42), y + G(2)), rot=0,
                      value="1R00")
        low = sh.place(R_LIB, r["RVb"], at=(jx + G(42), y + G(10)), rot=0,
                       value="47k0")
        sh.seg((jx + G(32), y), (rv.pin(1).x, y))
        sh.seg((rv.pin(1).x, y), rv.pin(1))
        sh.seg(rv.pin(2), low.pin(1))
        sh.seg(low.pin(2), (low.pin(2).x, y + G(16)))
        sh.gnd((low.pin(2).x, y + G(16)))
    note_block(sh, (jx + G(4), y - G(14)),
            "2u2 + 47k -> 1.5 Hz HP;  1k + 1n5 -> 106 kHz anti-alias.\n"
            "Trim sets full scale: 3.5 Vpk (2.5 Vrms) at wiper max, and only\n"
            "attenuates from there.  Overload is 0.70 FS = 1.7 Vrms in.\n"
            f"For a quieter source drop {r['Rin']}: FS = 2.5 V x "
            f"{r['Rin']}/{r['Rd1']}.",
            size=1.27)
    return rv


def quantiser(sh, XC, y, r, ch, v3=None, rows_labelled=True):
    """LM311 on a single supply, its four-resistor summing node and pull-up.

    The node sums the third integrator through Rs, the DAC through Rk0 -- the
    excess-loop-delay compensation -- and VREF_P through Rsh, with Rb to +5 V
    balancing it so the threshold lands exactly on VREF_P when the DAC sits at
    its mean.  `v3` is the third integrator, routed over the top of the
    resonator inverter into row 0 when given.

    `rows_labelled=False` leaves the row labels off so a testbench can wire
    its own sources straight onto the rows.

    Returns the row entry points by role.
    """
    cy = y
    rows = [(None, r["Rs"], "22k1"),
            (f"DACP_{ch}", r["Rk0"], "165k"),
            ("VREF_P", r["Rsh"], "22k1")]
    n = len(rows) + 1
    y_s = cy + (n - 1) * COL / 2.0
    y_s = round(y_s / 1.27) * 1.27
    bus_x = XC + G(21)
    cmp_u = sh.place("Comparator:LM311", r["Ucmp"], at=(XC + G(38), y_s - G(2)),
                     value="LM311")
    for i, (lbl, rref, rval) in enumerate(rows):
        ry = cy + i * COL
        rr = sh.place(R_LIB, rref, at=(XC + G(12), ry), rot=90, value=rval)
        sh.seg((XC, ry), rr.pin(1))
        sh.seg(rr.pin(2), (bus_x, ry))
        if lbl and rows_labelled:
            sh.label((XC, ry), lbl, kind="global")
    # the +5 V bias leg: equal to Rs, which is what centres the threshold
    ry = cy + 3 * COL
    rb = sh.place(R_LIB, r["Rb"], at=(XC + G(12), ry), rot=90, value="22k1")
    sh.seg((XC, ry), rb.pin(1))
    sh.rail((XC, ry), net="+5V", rise=0)
    sh.seg(rb.pin(2), (bus_x, ry))
    sh.seg((bus_x, cy), (bus_x, ry))
    sh.seg((bus_x, y_s), cmp_u.pin(3))
    # + input to the same +2.5 V the summing node is balanced about
    pp = cmp_u.pin(2)
    sh.seg(pp, (pp.x - G(5), pp.y))
    sh.seg((pp.x - G(5), pp.y), (pp.x - G(5), cy - G(8)))
    sh.seg((pp.x - G(5), cy - G(8)), (pp.x - G(12), cy - G(8)))
    plus_pt = (pp.x - G(12), cy - G(8))
    if rows_labelled:
        sh.label(plus_pt, "VREF_P", kind="global")
    # supplies: single +5 V, both grounds down
    v8 = cmp_u.pin(8)
    sh.seg(v8, (v8.x, v8.y - G(6)))
    sh.rail((v8.x, v8.y - G(6)), net="+5V", rise=STUB)
    for pn in (1, 4):
        p = cmp_u.pin(pn)
        sh.seg(p, (p.x, p.y + G(6)))
    sh.seg((cmp_u.pin(1).x, cmp_u.pin(1).y + G(6)),
           (cmp_u.pin(4).x, cmp_u.pin(4).y + G(6)))
    sh.gnd((cmp_u.pin(4).x, cmp_u.pin(4).y + G(6)))
    sh.nc(cmp_u.pin(5), cmp_u.pin(6))
    # open-collector output, pulled up, out to the flip-flop
    o = cmp_u.pin(7)
    sh.seg(o, (o.x + G(8), o.y))
    rpu = sh.place(R_LIB, r["Rpu"], at=(o.x + G(8), o.y - G(8)), rot=0,
                   value="2k21")
    sh.seg((o.x + G(8), o.y), rpu.pin(2))
    sh.seg(rpu.pin(1), (o.x + G(8), o.y - G(14)))
    sh.rail((o.x + G(8), o.y - G(14)), net="+5V", rise=STUB)
    sh.seg((o.x + G(8), o.y), (o.x + G(14), o.y))
    sh.label((o.x + G(14), o.y), f"CMP_{ch}", kind="global")
    note_block(sh, (XC - G(6), y - G(16)),
            "QUANTISER  (LM311 + retiming D-FF)\n"
            f"{r['Rk0']} is the excess-loop-delay compensation: without it the\n"
            "LM311's 200 ns costs 8 dB and most of the overload margin.\n"
            f"{r['Rb']} = {r['Rs']} is what centres the threshold on VREF_P.",
            size=1.27)

    # V3 also feeds the comparator: over the top, clear of the inverter
    if v3 is not None:
        top_y = y - G(10)
        sh.seg(v3["out"], (v3["out"][0] + G(2), v3["y_out"]))
        sh.seg((v3["out"][0] + G(2), v3["y_out"]),
               (v3["out"][0] + G(2), top_y))
        sh.seg((v3["out"][0] + G(2), top_y), (XC - G(4), top_y))
        sh.seg((XC - G(4), top_y), (XC - G(4), cy))
        sh.seg((XC - G(4), cy), (XC, cy))
    return {"v3": (XC, cy), "dacp": (XC, cy + COL), "vrefp": (XC, cy + 2 * COL),
            "plus": plus_pt, "u": cmp_u, "out": (o.x + G(14), o.y)}



def modulator(sh, ch, y, refs):
    """One complete channel. `refs` maps role -> refdes so L and R differ."""
    r = refs
    # kept short on purpose: a longer title overruns INTEGRATOR 1's caption
    note_block(sh, (G(16), y - G(26)),
               f"CHANNEL {ch}  -  3rd-order CT delta-sigma, fs 1.536 MHz, "
               f"OSR 32", size=2.0)

    # -- input: coupling, anti-alias, level trim -----------------------------
    jx = G(16)
    pot = front_end(sh, jx, y, r, ch)

    # -- three integrators ---------------------------------------------------
    X1, X2, X3 = G(76), G(136), G(196)
    i1 = summing_stage(sh, X1, y, [(None, r["Rin"], "20k5"),
                               (f"DACN_{ch}", r["Rd1"], "14k7"),
                               ("VREF_N", r["Ro1"], "14k7")],
                       r["U"], 1, "C", r["C1"], "220p",
                       title="INTEGRATOR 1  (a1 = 0.247)")
    wpr = pot.pin(2)                       # wiper sits 3.81 below the top pin
    sh.seg(wpr, (wpr.x + G(4), wpr.y))
    sh.seg((wpr.x + G(4), wpr.y), (wpr.x + G(4), y))
    sh.seg((wpr.x + G(4), y), (X1, y))

    i2 = summing_stage(sh, X2, y, [(None, r["R2"], "10k5"),
                               (f"DACP_{ch}", r["Rd2"], "13k0"),
                               ("VREF_N", r["Ro2"], "13k0"),
                               (None, r["Rg"], "255k")],
                       r["U"], 2, "C", r["C2"], "220p",
                       title="INTEGRATOR 2  (a2 = 0.321, + resonator)")
    elbow(sh, i1["out"], (X2, y), X2 - G(4))

    i3 = summing_stage(sh, X3, y, [(None, r["R3"], "5k90"),
                               (f"DACN_{ch}", r["Rd3"], "8k25"),
                               ("VREF_N", r["Ro3"], "8k25")],
                       r["U"], 3, "C", r["C3"], "220p",
                       title="INTEGRATOR 3  (a3 = 0.611)")
    elbow(sh, i2["out"], (X3, y), X3 - G(4))

    # -- resonator inverter: -V3 back into integrator 2 ----------------------
    XI = G(256)
    inv = summing_stage(sh, XI, y, [(None, r["Ri"], "10k0")],
                        r["U"], 4, "R", r["Rf"], "10k0",
                        title="RESONATOR INVERTER  (g = 0.0297)")
    elbow(sh, i3["out"], (XI, y), XI - G(4))

    # return path, right to left along the bottom, up into integrator 2 row 4
    ret_y = y + G(46)
    ox, oy = inv["out"]
    sh.seg((ox, oy), (ox, ret_y))
    sh.seg((ox, ret_y), (X2 - G(2), ret_y))
    sh.seg((X2 - G(2), ret_y), (X2 - G(2), y + 3 * COL))
    sh.seg((X2 - G(2), y + 3 * COL), (X2, y + 3 * COL))

    # -- comparator ----------------------------------------------------------
    quantiser(sh, G(320), y, r, ch, v3=i3)

    # -- TL074 package supply ------------------------------------------------
    sup = sh.place(TL07X, r["U"], at=(G(404), y + G(6)), unit=5,
                  value="TL074")
    vp, vn = sup.pin("V+"), sup.pin("V-")
    sh.seg(vp, (vp.x, vp.y - STUB))
    sh.rail((vp.x, vp.y - STUB), net="+5V", rise=STUB)
    sh.seg(vn, (vn.x, vn.y + STUB))
    sh.rail((vn.x, vn.y + STUB), net="-5V", rise=-STUB)
    cx = vp.x + G(10)
    ca = sh.place(C_LIB, r["Ca"], at=(cx, vp.y - STUB + G(3)), rot=0,
                  value="100n")
    cb = sh.place(C_LIB, r["Cb"], at=(cx, vn.y + STUB - G(3)), rot=0,
                  value="100n")
    sh.seg((vp.x, vp.y - STUB), (cx, vp.y - STUB))
    sh.seg((cx, vp.y - STUB), ca.pin(1))
    sh.seg(ca.pin(2), cb.pin(1))
    sh.seg(cb.pin(2), (cx, vn.y + STUB))
    sh.seg((vn.x, vn.y + STUB), (cx, vn.y + STUB))
    gy = round((ca.pin(2).y + cb.pin(1).y) / 2 / 1.27) * 1.27
    sh.seg((cx, gy), (cx + G(6), gy))
    sh.power("power:GND", (cx + G(6), gy), rot=270)
    ccmp = sh.place(C_LIB, r["Cc"], at=(G(430), y + G(6)), rot=0, value="100n")
    sh.seg(ccmp.pin(1), (G(430), y + G(2)))
    sh.rail((G(430), y + G(2)), net="+5V", rise=STUB)
    sh.gnd(ccmp.pin(2), drop=STUB)


def refs_for(ch, n):
    def k(p):
        return f"{p}{n}"
    return {"J": k("J"), "Cin": k("C"), "Caa": f"C{n+1}", "Raa": k("R"),
            "RV": k("RV"), "U": k("U"), "Ucmp": f"U{n+1}",
            "Rin": f"R{n+1}", "Rd1": f"R{n+2}", "Ro1": f"R{n+3}",
            "R2": f"R{n+4}", "Rd2": f"R{n+5}", "Ro2": f"R{n+6}",
            "Rg": f"R{n+7}", "R3": f"R{n+8}", "Rd3": f"R{n+9}",
            "Ro3": f"R{n+10}", "Ri": f"R{n+11}", "Rf": f"R{n+12}",
            "Rs": f"R{n+13}", "Rk0": f"R{n+14}", "Rsh": f"R{n+15}",
            "Rb": f"R{n+16}", "Rpu": f"R{n+17}",
            "C1": f"C{n+2}", "C2": f"C{n+3}", "C3": f"C{n+4}",
            "Ca": f"C{n+5}", "Cb": f"C{n+6}", "Cc": f"C{n+7}"}


# ===================================================================== build
#
# Every block function above takes the sheet as its first argument so the SPICE
# testbenches in ../sim can draw the SAME blocks. A bench that wires a stage
# differently from the board proves nothing about the board, and the only way
# to guarantee they agree is to call one function from both.

def write_project(sch_path, sheet_uuid):
    """Emit the .kicad_pro alongside the sheet.

    Two things here are load-bearing:

    * every netclass needs `wire_width`.  KiCad 10 applies the netclass wire
      width to every wire on the sheet and a MISSING key resolves to zero, so
      the drawing renders as a page of invisible wires and vanished junction
      dots while the netlist and ERC stay perfectly correct.
    * `sheets` must name the schematic's own root uuid.  If the project claims
      a different one, KiCad resolves symbols against the project's path, finds
      no instance data and drops them out of connectivity -- ERC then reports
      dozens of unconnected pins on a file kicad-cli reads as flawless.
    """
    import json
    pro = os.path.splitext(sch_path)[0] + ".kicad_pro"
    doc = {
        "board": {"design_settings": {}},
        "boards": [],
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": os.path.basename(pro), "version": 3},
        "net_settings": {
            "classes": [{
                "name": "Default",
                "bus_width": 12.0,
                "wire_width": 6.0,
                "line_style": 0,
                "clearance": 0.2,
                "track_width": 0.25,
                "via_diameter": 0.8,
                "via_drill": 0.4,
                "schematic_color": "rgba(0, 0, 0, 0.000)",
                "pcb_color": "rgba(0, 0, 0, 0.000)",
            }],
            "meta": {"version": 4},
        },
        "schematic": {
            "drawing": {
                "default_line_thickness": 6.0,
                "default_text_size": 50.0,
                "field_names": [],
                "intersheets_ref_show": False,
                "label_size_ratio": 0.375,
                "pin_symbol_size": 25.0,
                "text_offset_ratio": 0.15,
            },
            "meta": {"version": 1},
        },
        "sheets": [[sheet_uuid, "Root"]],
        "text_variables": {},
    }
    with open(pro, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    print("wrote", os.path.normpath(pro))


def main(bands="ABCD"):
    sh = new_sheet()
    # Band anchors are spaced from measured band extents (about 93 mm each),
    # not guessed: on A2 the four bands plus their captions only just fit.
    if "A" in bands:
        band_power(sh, G(27))
    if "B" in bands:
        band_digital(sh, G(109))
    if "C" in bands:
        modulator(sh, "L", G(191), refs_for("L", 20))
    if "D" in bands:
        modulator(sh, "R", G(269), refs_for("R", 60))
    links = sim_index(sh, G(150), G(56)) if bands == "ABCD" else {}

    problems = sh.check()
    if problems:
        print(f"{len(problems)} geometry problem(s):")
        for p in problems[:40]:
            print("   ", p)
    else:
        print("geometry OK")

    name = ("vinyl_adc.kicad_sch" if bands == "ABCD"
            else f"bisect_{bands}.kicad_sch")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", name)
    sh.emit(out)
    if links:
        add_hrefs(out, links)
    print("wrote", os.path.normpath(out))
    write_project(out, sh.uuid)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "ABCD"))
