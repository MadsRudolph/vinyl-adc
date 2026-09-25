#!/usr/bin/env python3
"""REV D: the converter as a Raspberry Pi HAT, on one fabricated 4-layer board.

    python3 tools/rev_d_layout.py   ->  rev_d/vinyl_adc_rev_d.kicad_sch

Rev C proved that one fabricated board holds the whole converter.  Rev D is
that board designed for a fab rather than merely permitted by one, and it is
drawn from the SAME block functions as the reference sheet and every milled
board (`vinyl_adc_layout.py`), so the modulator, the quantiser and the clock
tree cannot drift from what was measured.  What it adds, each with the
reason it earns its parts:

  * an ANALOG SUPPLY ISLAND, +5VA: a 10 uH choke and its own 470 u behind
    the +5V rail, feeding the op-amps, the comparators' bias, the DAC gates
    and the +/-2.5 V reference.  The DAC gates' supply IS the reference, and
    the bench measured the Pi's 5 V costing 6-11 dB of idle noise against a
    bench supply (bringup log 8.5); the charge pump's 30 mA at 192 kHz sat
    on that same rail.  The island keeps the reference ratiometric to the
    rail its gates run from (design-notes 6) while the switching current
    stays on the other side of the choke.
  * a SECOND 74HC244 in the charge pump: its 16 ohm output resistance is
    the drivers' on-resistance, so sixteen buffers halve it and lift the
    negative rail ~0.6 V -- the TL072 common-mode margin design-notes 10b
    called the one thing worth acting on.
  * a 33 ohm series damper in MCLK: one source, three loads spread over
    100 mm of board, and its edge is the jitter-critical one.
  * STATUS LEDS along the front edge: +5VA present, -5V present (the pump
    was a real bring-up fault), clock alive (a diode pump off a spare
    Schmitt gate -- lights only while LRCLK toggles), CLIP L / CLIP R
    (LM339 window comparators on the first integrator, stretched to ~1 s,
    because an overloaded 1-bit loop is what a vinyl click looks like), and
    three under the Pi's control (REC, BUSY, READY) since the Pi's own LEDs
    are hidden under the board.
  * two BUTTONS on the Pi: GPIO3 (shutdown, and wake from halt -- the
    canonical Pi trick) and GPIO23 (user: start/stop a rip).
  * the HAT ID EEPROM (24LC32, socketed, optional) with the write-protect
    jumper, on the ID_SD/ID_SC pins, so the board can carry its own overlay.
  * TEST POINTS on 2xN headers with a ground column, because the bench
    method here is two probes on header pins, never DIP legs.
  * a TONEARM / CHASSIS ground terminal with a lift network (10 R || 100 n
    || antiparallel diodes) and a jumper to bond it hard -- the 50 Hz hum
    open item in the bringup log.

The Pi plugs into a 2x20 socket on the copper side, HAT-style.  The sheet
is A0: the four bands as before (power, digital, channel L, channel R),
each channel's clip detector and test points drawn INSIDE its band, and
the board-level additions in one column to the right.  Nothing inside the
modulator loop changed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vinyl_adc_layout as L                                  # noqa: E402
from vinyl_adc_layout import (G, STUB, R_LIB, C_LIB, CP_LIB, LM358,  # noqa: E402
                              note_block, tie_low, ic_supply, opamp_supply,
                              band_power, band_digital, modulator, refs_for,
                              sim_index, emit_board, power_flags, TITLE)

NAME = "vinyl_adc_rev_d"

# The Pi's pins beyond the reference sheet's set.  Odd pins are the row
# nearer the Pi's centre and leave the symbol leftwards, even pins rightwards.
HAT_PINS = {27: "ID_SD", 28: "ID_SC",             # HAT ID EEPROM (I2C0)
            11: "LED_REC", 13: "LED_BUSY", 15: "LED_READY",   # GPIO17/27/22
            5: "BTN_SHDN",                         # GPIO3: shutdown + wake
            16: "BTN_USER"}                        # GPIO23

NPN, PNP = "Transistor_BJT:BC547", "Transistor_BJT:BC557"
LED, DIODE, SW = "Device:LED", "Device:D", "Switch:SW_Push"

# Rotation of a global label whose text must extend LEFT of its anchor (the
# anchor being the end of a stub that came from the right).  KiCad draws a
# 0-degree global label with its text to the right of the anchor.
LROT = 180

# per-channel refdes for the rev D additions: L, R
CLIP = {"L": dict(units=(1, 2), rpu="R48", d="D13", c="C42", rfill="R49",
                  rb="R50", q="Q2", rled="R52", led="D6", tp="J22"),
        "R": dict(units=(3, 4), rpu="R53", d="D14", c="C43", rfill="R59",
                  rb="R51", q="Q3", rled="R16", led="D7", tp="J62")}


def led_column(sh, x, ytop, rref, rval, dref, colour, source, sink="GND"):
    """One indicator: source at the top, series R, LED (anode up), sink.

    `source` is a rail name or ("label", net); `sink` is "GND" or a rail
    name drawn below.  The column is ytop..ytop+G(18) tall.
    """
    if isinstance(source, tuple):
        sh.seg((x - G(4), ytop), (x, ytop))
        sh.label((x - G(4), ytop), source[1], rot=LROT, kind="global")
    else:
        sh.rail((x, ytop), net=source, rise=STUB)
    r = sh.place(R_LIB, rref, at=(x, ytop + G(5)), rot=0, value=rval)
    sh.seg((x, ytop), r.pin(1))
    d = sh.place(LED, dref, at=(x, ytop + G(12)), rot=90, value=colour)
    sh.seg(r.pin(2), d.pin("A"))
    sh.seg(d.pin("K"), (x, ytop + G(18)))
    if sink == "GND":
        sh.gnd((x, ytop + G(18)), drop=0)
    else:
        sh.rail((x, ytop + G(18)), net=sink, rise=-STUB)


# ============================================================ POWER: ISLAND

def blk_island(sh, x, y):
    """+5V -> L2 -> +5VA, with the island's own reservoir.

    10 uH (the shop's "10u 3A" choke, low DCR) against 470 u is a 2.3 kHz
    corner: the pump's 192 kHz and the Pi's converter hash arrive 35-40 dB
    down.  The DC resistance is tens of milliohms, so the DAC's
    signal-dependent mean current (design-notes 6: "low impedance, not a
    series RC") drops microvolts across it -- three orders below the
    ratiometric cancellation it protects.  Q is about 1.5 with a low-ESR
    reservoir; the 3 dB peak at 2 kHz sits where the Pi's noise is not.
    """
    note_block(sh, (x - G(10), y - G(16)),
               "ANALOG ISLAND  +5VA  (10 uH + 470 u, fc 2.3 kHz)", size=2.0)
    sh.rail((x, y), net="+5V", rise=STUB)
    sh.seg((x, y), (x, y + G(4)))
    l2 = sh.place("Device:L", "L2", at=(x + G(6), y + G(4)), rot=90,
                  value="10u")
    la, lb = sorted(l2.pins, key=lambda q: q.x)
    sh.seg((x, y + G(4)), la)
    nx = x + G(14)
    sh.seg(lb, (nx, y + G(4)))
    sh.seg((nx, y + G(4)), (nx + G(16), y + G(4)))
    sh.rail((nx + G(16), y + G(4)), net="+5VA", rise=STUB)
    c18 = sh.place(CP_LIB, "C18", at=(nx, y + G(10)), rot=0, value="470u")
    c19 = sh.place(C_LIB, "C19", at=(nx + G(8), y + G(10)), rot=0,
                   value="100n")
    sh.seg((nx, y + G(4)), c18.pin(1))
    sh.seg((nx + G(8), y + G(4)), c19.pin(1))
    sh.seg(c18.pin(2), (nx, y + G(14)))
    sh.seg(c19.pin(2), (nx + G(8), y + G(14)))
    sh.seg((nx, y + G(14)), (nx + G(8), y + G(14)))
    sh.gnd((nx + G(4), y + G(14)))
    # the island is driven only through L2, so ERC needs telling it is a
    # supply; the reference's PWR_FLAG row lives at the band's far left
    power_flags(sh, nx + G(28), y - G(10), ("+5VA",))
    note_block(sh, (x - G(6), y + G(20)),
               "~35 dB down at the pump's 192 kHz.  Feeds the op-amps, the\n"
               "comparators' bias, the DAC gates and the reference, so the\n"
               "reference stays ratiometric to the gates' own rail.  Both\n"
               "chokes are the shop's 10u 3A part; L1 is the inlet from the\n"
               "Pi.  Neither is a resistor: DCR ~ 0.05 R keeps the DAC\n"
               "reference stiff (design-notes 6).", size=1.27)


# =========================================================== DIGITAL EXTRAS

def blk_mclk_damper(sh, x, y):
    """33 R in series with MCLK at its source.

    The 74HC4040's ~50 R output plus 33 R against three CMOS loads spread
    along 100 mm of track damps the edge's ring without slowing it
    measurably (33 R x 20 pF = 0.7 ns against a 650 ns period).  Same
    reasoning as the 475 R in the Pi lines, at a value that keeps the
    flip-flops' clock edge fast.
    """
    note_block(sh, (x - G(4), y - G(8)), "MCLK SOURCE DAMPING", size=2.0)
    sh.label((x, y), "MCLK_SRC", rot=LROT, kind="global")
    r = sh.place(R_LIB, "R14", at=(x + G(7), y), rot=90, value="33R2")
    ra, rb = sorted(r.pins, key=lambda q: q.x)
    sh.seg((x, y), ra)
    sh.seg(rb, (x + G(14), y))
    sh.label((x + G(14), y), "MCLK", kind="global")
    note_block(sh, (x - G(4), y + G(6)),
               "Divider Q1 -> 33R2 -> MCLK to both retiming flip-flops and the\n"
               "interleave mux.  Series damping at the one source; the edge\n"
               "is the jitter-critical one, so the value stays small.",
               size=1.27)


# ================================================================ THE HAT

def blk_hat_eeprom(sh, x, y):
    """24LC32 on ID_SD / ID_SC: the HAT's own device-tree overlay.

    A0-A2 low (address 0x50, where the Pi looks), WP pulled up so the
    contents survive, J6 shorted to ground WP for programming.  Pull-ups on
    the ID lines are on the Pi (3k9), so none here.  Socketed and optional:
    the board works without it, the Pi just needs `dtoverlay=vinyl-adc` in
    config.txt as today.
    """
    note_block(sh, (x - G(4), y - G(16)),
               "HAT ID EEPROM  (optional; 24LC32 DIP-8, ORDER)", size=2.0)
    u = sh.place("Memory_EEPROM:24LC32", "U11", at=(x + G(24), y + G(12)),
                 value="24LC32")
    tie_low(sh, u.pin("A0"), u.pin("A1"), u.pin("A2"))
    ic_supply(sh, u, "VCC", "GND", "C45", u.pin("A0").x - G(10), rail="+3V3")
    for name, net in (("SDA", "ID_SD"), ("SCL", "ID_SC")):
        p = u.pin(name)
        sh.seg(p, (p.x + G(6), p.y))
        sh.label((p.x + G(6), p.y), net, kind="global")
    wp = u.pin("WP")
    wx = wp.x + G(14)                  # clear of the SDA/SCL label text
    sh.seg(wp, (wx, wp.y))
    r = sh.place(R_LIB, "R15", at=(wx, wp.y - G(6)), rot=0, value="3k92")
    sh.seg((wx, wp.y), r.pin(2))
    sh.rail(r.pin(1), net="+3V3", rise=STUB)
    j = sh.place("Connector_Generic:Conn_01x02", "J6", at=(wx + G(8), wp.y),
                 value="WP")
    sh.seg((wx, wp.y), j.pin(1))
    p2 = j.pin(2)
    sh.seg(p2, (p2.x - G(2), p2.y))
    sh.gnd((p2.x - G(2), p2.y), drop=STUB)
    note_block(sh, (x - G(4), y + G(30)),
               "J6 open = write-protected (normal).  Short J6 to program\n"
               "the overlay with eepflash.sh; then open it again.",
               size=1.27)


def blk_buttons(sh, x, y):
    """Two momentary buttons to the Pi, each 1 k in series and 100 n across.

    GPIO3 has the Pi's own 1k8 pull-up and, halted, wakes the Pi when
    pulled low -- so SW1 is both the clean-shutdown button
    (dtoverlay=gpio-shutdown) and the power button.  GPIO23 wants the
    internal pull-up (gpiozero Button does that).  The 1 k saves the GPIO
    if it is ever configured as an output; 100 n x 1k8 is a 180 us
    debounce.
    """
    note_block(sh, (x - G(4), y - G(16)), "BUTTONS  (to the Pi)", size=2.0)
    rows = (("BTN_SHDN", "R57", "SW1", "C46", "SHUTDOWN / WAKE  GPIO3"),
            ("BTN_USER", "R58", "SW2", "C47", "USER  GPIO23"))
    for i, (net, rref, sref, cref, cap) in enumerate(rows):
        ry = y + G(4) + i * G(20)
        sh.label((x, ry), net, rot=LROT, kind="global")
        r = sh.place(R_LIB, rref, at=(x + G(7), ry), rot=90, value="1k00")
        ra, rb = sorted(r.pins, key=lambda q: q.x)
        sh.seg((x, ry), ra)
        node = (x + G(14), ry)
        sh.seg(rb, node)
        sw = sh.place(SW, sref, at=(x + G(22), ry), value=cap)
        sa, sb = sorted((sw.pin(1), sw.pin(2)), key=lambda q: q.x)
        sh.seg(node, sa)
        sh.seg(sb, (x + G(30), ry))
        c = sh.place(C_LIB, cref, at=(x + G(14), ry + G(5)), rot=0,
                     value="100n")
        sh.seg(node, c.pin(1))
        sh.seg(c.pin(2), (x + G(14), ry + G(10)))
        sh.seg((x + G(30), ry), (x + G(30), ry + G(10)))
        sh.seg((x + G(14), ry + G(10)), (x + G(30), ry + G(10)))
        sh.gnd((x + G(22), ry + G(10)))


# ============================================================ STATUS LEDS

def blk_status_leds(sh, x, y):
    """The five plain indicators; CLK and the two CLIP LEDs are drawn with
    the detectors that drive them.

    1 k from a 5 V rail is ~3 mA; 330 R from a 3.3 V GPIO is the same
    3 mA, well inside the Pi's 8 mA default drive.  The -5V indicator runs
    from ground DOWN to the pump rail, so it is the one LED that says the
    charge pump is actually pumping.
    """
    note_block(sh, (x - G(4), y - G(16)),
               "STATUS LEDS  (front edge; CLK and CLIP L/R are with their "
               "detectors)", size=2.0)
    cols = (("R40", "1k00", "D3", "GREEN", "+5VA", "GND"),
            ("R41", "1k00", "D4", "YELLOW", "GND_TOP", "-5V"),
            ("R54", "330R", "D8", "RED", ("label", "LED_REC"), "GND"),
            ("R55", "330R", "D9", "YELLOW", ("label", "LED_BUSY"), "GND"),
            ("R56", "330R", "D10", "GREEN", ("label", "LED_READY"), "GND"))
    for i, (rref, rval, dref, colour, src, sink) in enumerate(cols):
        cx = x + G(8) + i * G(18)
        if src == "GND_TOP":
            # current flows from ground down into the -5V rail
            sh.power("power:GND", (cx, y), rot=180)
            r = sh.place(R_LIB, rref, at=(cx, y + G(5)), rot=0, value=rval)
            sh.seg((cx, y), r.pin(1))
            d = sh.place(LED, dref, at=(cx, y + G(12)), rot=90, value=colour)
            sh.seg(r.pin(2), d.pin("A"))
            sh.seg(d.pin("K"), (cx, y + G(18)))
            sh.rail((cx, y + G(18)), net=sink, rise=-STUB)
        else:
            led_column(sh, cx, y, rref, rval, dref, colour, src, sink)
    for i, cap in enumerate(("+5VA", "-5V", "REC", "BUSY", "READY")):
        sh.note((x + G(5) + i * G(18), y + G(25)), cap, size=1.27)


def blk_clock_detector(sh, x, y):
    """CLK LED: lights only while the clock tree is actually running.

    U3B (a spare 74HCT132 gate, both inputs on LRCLK) drives a 1n5 into a
    two-diode pump; 48 kHz x 1n5 x 5 V is 0.36 mA, which through 10 k
    holds the BC547 hard on -- the 10 u settles near +3 V and the LED runs
    at ~3 mA from 1 k.  Clock gone: the 10 u drains through the base in
    ~100 ms and the LED is out.  A stuck-high or stuck-low LRCLK reads as
    "no clock", which is the point -- a plain LED on the clock line would
    glow half-bright forever.
    """
    note_block(sh, (x - G(4), y - G(30)),
               "CLOCK ALIVE  (diode pump off LRCLK: on only while it toggles)",
               size=2.0)
    ry = y
    sh.label((x, ry), "LRCLK_N", rot=LROT, kind="global")
    c40 = sh.place(C_LIB, "C40", at=(x + G(7), ry), rot=90, value="1n5")
    ca, cb = sorted(c40.pins, key=lambda q: q.x)
    sh.seg((x, ry), ca)
    n1 = (x + G(14), ry)
    sh.seg(cb, n1)
    d11 = sh.place(DIODE, "D11", at=(x + G(14), ry + G(6)), rot=270,
                   value="1N4148")
    sh.seg(n1, d11.pin("K"))
    sh.gnd(d11.pin("A"), drop=G(3))
    d12 = sh.place(DIODE, "D12", at=(x + G(20), ry), rot=180, value="1N4148")
    sh.seg(n1, d12.pin("A"))
    n2 = (x + G(26), ry)
    sh.seg(d12.pin("K"), n2)
    c41 = sh.place(CP_LIB, "C41", at=(x + G(26), ry + G(6)), rot=0,
                   value="10u")
    sh.seg(n2, c41.pin(1))
    sh.gnd(c41.pin(2), drop=G(3))
    r43 = sh.place(R_LIB, "R43", at=(x + G(33), ry), rot=90, value="10k0")
    ra, rb = sorted(r43.pins, key=lambda q: q.x)
    sh.seg(n2, ra)
    q = sh.place(NPN, "Q1", at=(x + G(41), ry), value="BC547")
    sh.seg(rb, q.pin("B"))
    sh.gnd(q.pin("E"), drop=G(3))
    c = q.pin("C")
    sh.seg(c, (c.x, ry - G(8)))
    d5 = sh.place(LED, "D5", at=(c.x, ry - G(11)), rot=90, value="GREEN")
    sh.seg(d5.pin("K"), (c.x, ry - G(8)))
    r42 = sh.place(R_LIB, "R42", at=(c.x, ry - G(18)), rot=0, value="1k00")
    sh.seg(d5.pin("A"), r42.pin(2))
    sh.rail(r42.pin(1), net="+5VA", rise=STUB)
    sh.note((c.x + G(4), ry - G(11)), "CLK", size=1.27)


# ============================================================ CLIP DETECT

def blk_clip_common(sh, x, y):
    """The two thresholds both channels compare against, and U12's supply.

    +/-2.0 V, derived from the +/-2.5 V references by 22k1 over 100k
    (0.82) so they track the same rail as full scale does.  The first
    integrator swings 1.4-1.9 V at the design levels and saturates at
    +3.2 / -2.35 V (design-notes 10c); +/-2.0 V is inside saturation on the
    tight negative side and past the -4.4 dBFS peaks -- a clip LED that
    says "back the trim off" before the loop actually latches.  The LM339
    runs +5VA / -5V so a -2 V input is in range.
    """
    note_block(sh, (x - G(4), y - G(16)),
               "CLIP THRESHOLDS  (+/-2.0 V from the references) and the "
               "LM339's supply", size=2.0)
    for i, (src, rs, rp, net) in enumerate((("VREF_P", "R44", "R45", "TH_P"),
                                            ("VREF_N", "R46", "R47", "TH_N"))):
        ty = y + i * G(14)
        sh.label((x, ty), src, rot=LROT, kind="global")
        r = sh.place(R_LIB, rs, at=(x + G(7), ty), rot=90, value="22k1")
        ra, rb = sorted(r.pins, key=lambda q: q.x)
        sh.seg((x, ty), ra)
        node = (x + G(14), ty)
        sh.seg(rb, node)
        rq = sh.place(R_LIB, rp, at=(x + G(14), ty + G(5)), rot=0,
                      value="100k")
        sh.seg(node, rq.pin(1))
        sh.gnd(rq.pin(2), drop=G(2))
        sh.seg(node, (x + G(20), ty))
        sh.label((x + G(20), ty), net, kind="global")
    note_block(sh, (x - G(4), y + G(26)),
               "TH_P = +2.47 x 100/122.1 = +2.02 V\n"
               "TH_N = -2.43 x 100/122.1 = -1.99 V", size=1.27)
    opamp_supply(sh, "U12", (x + G(52), y + G(6)), "C44", "C50", unit=5,
                 lib="Comparator:LM339", value="LM339", rail="+5VA")


def blk_clip_channel(sh, x, y, ch, r):
    """CLIP ch: two LM339 sections wired-OR on the first integrator,
    stretched to ~1 s, driving the front-panel LED.  Drawn in its channel's
    band, under the front end.

    Open collectors, 10 k up; a 1N4148 dumps the 10 u stretch cap when
    either section fires, 100 k refills it (tau 1 s), and a BC557 lights
    the LED while the cap is low.  The LM339's inputs draw 25 nA from the
    integrator output, which is an op-amp output and does not notice.
    """
    note_block(sh, (x - G(4), y - G(18)),
               f"CLIP {ch}  (window on INT1_{ch} against TH_P / TH_N)",
               size=2.0)
    cx = x + G(20)
    ua = sh.place("Comparator:LM339", "U12", at=(cx, y), unit=r["units"][0],
                  value="LM339")
    ub = sh.place("Comparator:LM339", "U12", at=(cx, y + G(12)),
                  unit=r["units"][1], value="LM339")
    oa = ua.pin({1: 2, 3: 13}[r["units"][0]])
    ob = ub.pin({2: 1, 4: 14}[r["units"][1]])
    for p, net in ((ua.pin("+"), f"INT1_{ch}"), (ua.pin("-"), "TH_P"),
                   (ub.pin("+"), "TH_N"), (ub.pin("-"), f"INT1_{ch}")):
        sh.seg(p, (p.x - G(6), p.y))
        sh.label((p.x - G(6), p.y), net, rot=LROT, kind="global")
    # wired-OR of the two open collectors, pulled up
    ox = oa.x + G(4)
    sh.seg(oa, (ox, oa.y))
    sh.seg(ob, (ox, ob.y))
    sh.seg((ox, oa.y), (ox, ob.y))
    pu = sh.place(R_LIB, r["rpu"], at=(ox, oa.y - G(6)), rot=0, value="10k0")
    sh.seg((ox, oa.y), pu.pin(2))
    sh.rail(pu.pin(1), net="+5VA", rise=STUB)
    # stretcher: diode dumps the cap when the OR node goes low
    sh.seg((ox, ob.y), (ox + G(4), ob.y))
    d = sh.place(DIODE, r["d"], at=(ox + G(8), ob.y), rot=0, value="1N4148")
    sh.seg((ox + G(4), ob.y), d.pin("K"))
    sx = ox + G(14)
    s = (sx, ob.y)
    sh.seg(d.pin("A"), s)
    c = sh.place(CP_LIB, r["c"], at=(sx, ob.y + G(6)), rot=0, value="10u")
    sh.seg(s, c.pin(1))
    sh.gnd(c.pin(2), drop=G(3))
    rf = sh.place(R_LIB, r["rfill"], at=(sx, ob.y - G(6)), rot=0, value="100k")
    sh.seg(s, rf.pin(2))
    sh.rail(rf.pin(1), net="+5VA", rise=STUB)
    # PNP: base low -> LED on.  Drawn emitter-up (mirror x), as a high-side
    # switch reads.
    rbase = sh.place(R_LIB, r["rb"], at=(sx + G(7), ob.y), rot=90,
                     value="10k0")
    ra, rb2 = sorted(rbase.pins, key=lambda q: q.x)
    sh.seg(s, ra)
    q = sh.place(PNP, r["q"], at=(sx + G(15), ob.y), mirror="x",
                 value="BC557")
    sh.seg(rb2, q.pin("B"))
    e, col = q.pin("E"), q.pin("C")
    sh.rail(e, net="+5VA", rise=STUB)
    sh.seg(col, (col.x, col.y + G(2)))
    rl = sh.place(R_LIB, r["rled"], at=(col.x, col.y + G(5)), rot=0,
                  value="1k00")
    sh.seg((col.x, col.y + G(2)), rl.pin(1))
    dl = sh.place(LED, r["led"], at=(col.x, col.y + G(12)), rot=90,
                  value="RED")
    sh.seg(rl.pin(2), dl.pin("A"))
    sh.gnd(dl.pin("K"), drop=G(2))
    sh.note((col.x + G(4), col.y + G(12)), f"CLIP {ch}", size=1.27)


# ======================================================== CHASSIS / TEST

def blk_chassis(sh, x, y):
    """Tonearm / chassis ground with a lift network.

    Both terminal pins are CHASSIS.  J4 shorted bonds it straight to the
    signal ground, which is the milled stack's star-ground arrangement.  J4
    open leaves 10 R || 100 n || two antiparallel 1N4003: audio-frequency
    hum current sees 10 R instead of a dead short, RF still goes to ground
    through the 100 n, and anything over 0.7 V is clamped by the diodes
    so the two grounds can never drift apart far enough to matter.
    """
    note_block(sh, (x - G(4), y - G(16)),
               "TONEARM / CHASSIS GROUND  (J4 shorted = hard bond; open = "
               "lift network)", size=2.0)
    j = sh.place("Connector:Screw_Terminal_01x02", "J3", at=(x, y + G(2)),
                 mirror="y", value="TONEARM GND")
    p1, p2 = j.pin(1), j.pin(2)
    bx = p1.x + G(6)
    sh.seg(p1, (bx, p1.y))
    sh.seg(p2, (bx, p2.y))
    sh.seg((bx, p2.y), (bx, p1.y))
    yt, yb = p1.y, p1.y + G(12)
    legs = ((R_LIB, "R17", "10R0", 0), (C_LIB, "C48", "100n", 0),
            (DIODE, "D15", "1N4003", 90), (DIODE, "D16", "1N4003", 270))
    lx = bx + G(6)
    for i, (lib, ref, val, rot) in enumerate(legs):
        px = lx + i * G(6)
        part = sh.place(lib, ref, at=(px, yt + G(6)), rot=rot, value=val)
        top, bot = sorted(part.pins, key=lambda q: q.y)
        sh.seg((px, yt), top)
        sh.seg(bot, (px, yb))
    jx = lx + 4 * G(6)
    jp = sh.place("Connector_Generic:Conn_01x02", "J4", at=(jx + G(4), yt + G(4)),
                  value="GND LIFT")
    sh.seg((jx, yt), jp.pin(1))
    sh.seg(jp.pin(2), (jx, yb))
    sh.seg((bx, yt), (jx, yt))
    sh.seg((lx, yb), (jx, yb))         # from the first leg: nothing meets
                                       # the rail at bx, and a rail end that
                                       # ends on nothing is an ERC warning
    sh.label((bx, yt), "CHASSIS", rot=90, kind="global")
    sh.gnd((lx + G(9), yb))
    note_block(sh, (x - G(4), yb + G(8)),
               "D15/D16 conduct CHASSIS <-> GND above 0.7 V either way;\n"
               "10R0 carries hum current, 100n carries RF.  Enclosure post\n"
               "and the turntable's spade both land on J3.", size=1.27)


def tp_header(sh, x, y, ref, cap, sigs):
    """One 2xN header, odd column all GND: a probe ground beside every
    signal.  Two probes on header pins, never DIP legs."""
    n = len(sigs)
    j = sh.place(f"Connector_Generic:Conn_02x{n:02d}_Odd_Even", ref,
                 at=(x + G(8), y + G(8)), value=cap)
    gnds = [j.pin(2 * i + 1) for i in range(n)]
    gx = gnds[0].x - G(6)
    for p in gnds:
        sh.seg(p, (gx, p.y))
    sh.seg((gx, gnds[0].y), (gx, gnds[-1].y))
    sh.gnd((gx, gnds[-1].y), drop=STUB)
    for i, sig in enumerate(sigs):
        p = j.pin(2 * i + 2)
        sh.seg(p, (p.x + G(6), p.y))
        sh.label((p.x + G(6), p.y), sig, kind="global")


def blk_tp_channel(sh, x, y, ch, ref):
    note_block(sh, (x - G(4), y - G(6)), f"TEST POINTS {ch}  (odd pins GND)",
               size=1.6)
    tp_header(sh, x, y, ref, f"TP {ch}",
              tuple(f"{s}_{ch}" for s in ("INT1", "INT2", "INT3", "CMP", "DACP")))


def blk_tp_digital(sh, x, y):
    note_block(sh, (x - G(4), y - G(16)),
               "TEST POINTS, DIGITAL AND REFERENCE  (odd pins GND)", size=2.0)
    tp_header(sh, x, y, "J5", "TP DIG", ("MCLK", "LRCLK", "DIN", "VREF_P",
                                         "VREF_N"))


# ================================================================== BOARD

# band origins: the four bands as the reference sheet, spaced for the
# second pump package in the power band
# channel R sits G(126) below L, not the reference sheet's G(110): the clip
# detector drawn under each channel's front end needs the extra rows
Y_POWER, Y_DIGITAL, Y_L, Y_R = G(27), G(140), G(250), G(376)
X_COL = G(446)                 # the column of board-level additions


def board_rev_d(sh):
    band_power(sh, Y_POWER, ref_opamp=LM358, ref_rail="+5VA",
               pump_second=("U10", "C49"))
    blk_island(sh, G(380), Y_POWER)
    band_digital(sh, Y_DIGITAL, pi40=True, hat=HAT_PINS,
                 detector=("LRCLK", "LRCLK_N"), mclk_label="MCLK_SRC",
                 inlet=("L1", "Device:L", "10u"))
    blk_mclk_damper(sh, G(190), Y_DIGITAL + G(54))
    for ch, y in (("L", Y_L), ("R", Y_R)):
        modulator(sh, ch, y, refs_for(ch, 20 if ch == "L" else 60),
                  rail="+5VA", int_labels=True)
        blk_clip_channel(sh, G(20), y + G(62), ch, CLIP[ch])
        blk_tp_channel(sh, G(236), y + G(60), ch, CLIP[ch]["tp"])

    x = X_COL
    blk_hat_eeprom(sh, x, G(27))
    blk_buttons(sh, x, G(84))
    blk_status_leds(sh, x, G(142))
    blk_clock_detector(sh, x, G(208))
    blk_clip_common(sh, x, G(254))
    blk_chassis(sh, x, G(310))
    blk_tp_digital(sh, x, G(366))
    return sim_index(sh, x, G(406))


def footprints():
    """Footprints for the parts the reference sheet never had."""
    L.FOOTPRINTS.update({
        # the shop's "10u 3A" choke: an axial part on a 15.24 mm pitch fits
        # whatever body it turns out to have; a radial one bends in
        "Device:L": "Inductor_THT:L_Axial_L12.0mm_D5.0mm_P15.24mm_Horizontal"
                    "_Fastron_MISC",
        "Device:LED": "LED_THT:LED_D5.0mm",
        NPN: "Package_TO_SOT_THT:TO-92_Inline",
        PNP: "Package_TO_SOT_THT:TO-92_Inline",
        SW: "Button_Switch_THT:SW_PUSH_6mm",
        "Memory_EEPROM:24LC32": L.FP_DIP.format(8),
        "Comparator:LM339": L.FP_DIP.format(14),
        "Connector_Generic:Conn_02x05_Odd_Even":
            "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical",
        "Connector_Generic:Conn_01x02":
            "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    })
    L.FOOTPRINTS_V.update({
        "1N4148": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
        "1N4003": "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
    })
    L.FOOTPRINTS_C.update({"10u": "Capacitor_THT:CP_Radial_D5.0mm_P2.50mm"})


def main():
    footprints()
    return emit_board(NAME, board_rev_d, "A0",
                      TITLE + "  -  REV D, RASPBERRY PI HAT, ONE 4-LAYER BOARD")


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
