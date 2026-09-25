#!/usr/bin/env python3
"""Gate: the rev D board IS the reference sheet, plus exactly what it claims.

    python3 tools/check_rev_d.py [vinyl_adc_rev_e]

The optional name gates a board drawn from the same blocks in other
packages (rev E, the SMD HAT): its netlist must pass every check here.

Same method as check_rev_c.py: weld every part rev D puts IN SERIES with a
reference net (L2 between +5V and +5VA, R12/R13 in the Pi clock lines, R14
in MCLK), drop every part the reference sheet does not have, and require
the partition of every remaining (ref, pin) node to be IDENTICAL.  The
dropped set is computed, not listed, so a new part cannot hide -- it is
printed so the reader can see it is only the additions.

Three nodes are dropped by name: U3's second gate, which the reference
ties low and rev D uses as the clock-alive buffer.  Everything else that
rev D adds hangs off existing nets by its own pins and vanishes with them.

Then the additions are asserted directly: the island choke really sits
between +5V and +5VA and the loop's supply pins are on the island; the
clip detector really reads the first integrators; the buttons and LEDs
really reach the Pi pins they claim; the second pump package really
parallels the first.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                  # noqa: E402
from check_intent import load, netof                          # noqa: E402
from check_split import describe                              # noqa: E402
from check_rev_c import groups                                # noqa: E402

REF = "vinyl_adc"
REVD = sys.argv[1] if len(sys.argv) > 1 else "vinyl_adc_rev_d"
SERIES = ("L2", "R12", "R13", "R14")
DROP_NODES = {("U3", "4"), ("U3", "5"), ("U3", "6")}


def refs_of(nets):
    return {r for nodes in nets.values() for r, _ in nodes
            if not r.startswith("#")}


def strip(gs, nodes):
    out = set()
    for g in gs:
        h = frozenset(g - nodes)
        if h:
            out.add(h)
    return out


def main():
    ref = load(paths.net(REF), paths.sch(REF))
    revd = load(paths.net(REVD), paths.sch(REVD))
    added = refs_of(revd) - refs_of(ref)
    drop = added | {"J2"}          # welded parts vanish too, as in rev C
    want = strip(groups(ref, drop=drop), DROP_NODES)
    got = strip(groups(revd, weld=SERIES, drop=drop), DROP_NODES)
    fail = []
    for g in sorted(want - got, key=describe):
        near = max(got, key=lambda h: len(h & g), default=frozenset())
        fail.append("net missing from rev D: " + describe(g)
                    + ("\n        nearest: " + describe(near) if near & g else ""))
    for g in sorted(got - want, key=describe):
        fail.append("net the reference does not have: " + describe(g))

    def on(ref_, pin):
        return netof(revd, ref_, pin)

    def expect(cond, msg):
        if not cond:
            fail.append(msg)

    # the island: L2 from +5V to +5VA, and the loop's supply pins on it
    expect({on("L2", "1"), on("L2", "2")} == {"+5V", "+5VA"},
           f"L2 is on {on('L2', '1')} / {on('L2', '2')}, not +5V / +5VA")
    for u in ("U20", "U22", "U60", "U62", "U2"):
        expect(on(u, "8") == "+5VA", f"{u} V+ is on {on(u, '8')}, not +5VA")
    for u in ("U21", "U61"):
        expect(on(u, "8") == "+5VA", f"{u} V+ is on {on(u, '8')}, not +5VA")
    for u in ("U24", "U64", "U23", "U63"):      # the loop's logic, too
        expect(on(u, "14") == "+5VA", f"{u} VCC is on {on(u, '14')}, not +5VA")
    for u in ("U1", "U10", "U3", "U4", "U6", "U9"):
        expect(on(u, "20" if u in ("U1", "U10") else
                     "16" if u in ("U4", "U6") else "14") == "+5V",
               f"{u} VCC is not on +5V")
    expect(on("R2", "1") == "+5VA", "reference divider R2 is not on +5VA")
    # the inlet: Pi 5 V pins -> L1 -> +5V
    expect(on("J2", "2") == on("J2", "4") == on("L1", "1") == "PI_5V",
           "the Pi's 5 V pins do not reach L1 as PI_5V")
    expect(on("L1", "2") == "+5V", "L1 does not feed +5V")
    # the second pump package parallels the first
    for a, b in (("2", "2"), ("18", "18"), ("11", "11"), ("9", "9")):
        expect(on("U10", a) == on("U1", b),
               f"U10.{a} is on {on('U10', a)}, U1.{b} on {on('U1', b)}")
    expect(on("U1", "18") == on("C4", "1"),
           "the pump outputs do not drive the flying capacitor")
    # MCLK damper
    expect(on("R14", "1") == "MCLK_SRC" and on("R14", "2") == "MCLK"
           or on("R14", "2") == "MCLK_SRC" and on("R14", "1") == "MCLK",
           "R14 is not between MCLK_SRC and MCLK")
    expect(on("U4", "7") == "MCLK_SRC", "the divider's Q1 is not MCLK_SRC")
    for u in ("U23", "U63", "U6"):
        pin = "1" if u == "U6" else "3"
        expect(on(u, pin) == "MCLK", f"{u}.{pin} is on {on(u, pin)}, not MCLK")
    # clip detector reads the first integrators, thresholds off the references
    expect(on("U12", "5") == on("U20", "1") == "INT1_L",
           "U12A + is not on INT1_L")
    expect(on("U12", "6") == "INT1_L", "U12B - is not on INT1_L")
    expect(on("U12", "11") == on("U60", "1") == "INT1_R",
           "U12C + is not on INT1_R")
    expect(on("U12", "8") == "INT1_R", "U12D - is not on INT1_R")
    expect(on("U12", "4") == on("U12", "10") == "TH_P", "TH_P wiring")
    expect(on("U12", "7") == on("U12", "9") == "TH_N", "TH_N wiring")
    expect(on("R44", "1") == "VREF_P" and on("R46", "1") == "VREF_N",
           "thresholds are not derived from VREF_P / VREF_N")
    expect(on("U12", "3") == "+5VA" and on("U12", "12") == "-5V",
           "LM339 supply is not +5VA / -5V")
    # the Pi's extra pins
    for pin, net in ((27, "ID_SD"), (28, "ID_SC"), (11, "LED_REC"),
                     (13, "LED_BUSY"), (15, "LED_READY"), (5, "BTN_SHDN"),
                     (16, "BTN_USER")):
        expect(on("J2", str(pin)) == net,
               f"J2.{pin} is on {on('J2', str(pin))}, not {net}")
    expect(on("U11", "5") == "ID_SD" and on("U11", "6") == "ID_SC",
           "EEPROM SDA/SCL are not on ID_SD/ID_SC")
    expect(on("U11", "8") == "+3V3", "EEPROM VCC is not +3V3")
    # clock-alive detector fed from U3's second gate
    expect(on("U3", "4") == on("U3", "5") == "LRCLK",
           "U3B inputs are not both on LRCLK")
    expect(on("U3", "6") == "LRCLK_N" == on("C40", "1"),
           "U3B output does not drive the pump capacitor")
    # chassis
    expect(on("J3", "1") == on("J3", "2") == "CHASSIS", "J3 is not CHASSIS")
    expect({on("J4", "1"), on("J4", "2")} == {"CHASSIS", "GND"},
           "J4 does not bridge CHASSIS to GND")
    u2 = set(re.findall(r'\(ref "U2"\)\s*\(value "([^"]+)"\)',
                        open(paths.net(REVD), encoding="utf-8").read()))
    expect(u2 == {"LM358"}, f"U2 is {u2}, rev D wants the LM358")

    print(f"reference {len(want)} nets, rev D {len(got)} nets after welding "
          f"{', '.join(SERIES)} and dropping {len(drop)} added parts:")
    print("   " + " ".join(sorted(drop, key=lambda r: (re.sub(r'\d', '', r),
                                                       int(re.sub(r'\D', '', r) or 0)))))
    if fail:
        print(f"FAIL  {len(fail)} problem(s):")
        for f in fail:
            print("   -", f)
        return 1
    print(f"OK    {REVD} is the reference sheet plus the island, the second "
          "pump, R14, the HAT pins, LEDs, buttons, EEPROM, chassis and TPs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
