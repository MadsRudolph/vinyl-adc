#!/usr/bin/env python3
"""Bill of materials for rev E, the SMD HAT, straight from its netlist.

    python3 tools/make_bom_smd.py > ../../docs/bom-rev-e.md

Rev D's BOM is checked against the DTU shop's drawers; rev E's parts come
from a distributor (or PCBWay's assembly service), so each line carries the
package, the spec that matters and one example part number.  The examples
are common catalogue parts, not a sourcing decision: anything meeting the
spec column fits the footprint.
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                  # noqa: E402

NAME = "vinyl_adc_rev_e"

# value -> (spec, example part number); resistors and small caps are done
# by rule below
PARTS = {
    "TL072": ("dual JFET op-amp, SOIC-8", "TI TL072CDR"),
    "LM311": ("comparator, SOIC-8", "TI LM311DR"),
    "LM358": ("dual op-amp, SOIC-8", "TI LM358DR"),
    "LM339": ("quad comparator, SOIC-14", "TI LM339DR"),
    "74HC04": ("hex inverter, SOIC-14", "Nexperia 74HC04D"),
    "74HCU04": ("unbuffered hex inverter, SOIC-14 (Pierce oscillator)",
                "Nexperia 74HCU04D"),
    "74HC74": ("dual D flip-flop, SOIC-14", "Nexperia 74HC74D"),
    "74HCT132": ("quad Schmitt NAND, SOIC-14", "Nexperia 74HCT132D"),
    "74HC157": ("quad 2:1 mux, SOIC-16", "Nexperia 74HC157D"),
    "74HC4040": ("12-stage counter, SOIC-16", "Nexperia 74HC4040D"),
    "74HC4049": ("hex inverter / level shifter, SOIC-16",
                 "Nexperia 74HC4049D"),
    "74HC244": ("octal buffer, SOIC-20 wide (7.5 mm)", "Nexperia 74HC244D"),
    "24LC32": ("32 kbit I2C EEPROM, SOIC-8 (optional)",
               "Microchip 24LC32A-I/SN"),
    "BC847": ("NPN, SOT-23", "BC847B"),
    "BC857": ("PNP, SOT-23", "BC857B"),
    "1N4148W": ("small-signal diode, SOD-123", "1N4148W"),
    "SS14": ("1 A 40 V Schottky, SMA", "SS14"),
    "S1M": ("1 A rectifier, SMA", "S1M"),
    "6.144MHz": ("crystal, HC-49/SMD, 18-20 pF load (C16/C17 27p)",
                 "any 6.144 MHz HC-49/SMD"),
    "RASPBERRY PI 4": ("2x20 female header, 2.54 mm, THT, on the copper side",
                       "Samtec SSQ-120 / any 8.5 mm HAT socket"),
}
L10U = ("10 uH shielded power inductor, 12 x 12 mm, >= 1 A, low DCR",
        "Bourns SRR1260-100M")
CAPS = {
    "100n": ("X7R 50 V, 0805", "any 0805 X7R 100 nF"),
    "1n5": ("C0G/NP0 50 V, 0805", "any 0805 C0G 1.5 nF"),
    "220p": ("C0G/NP0 50 V, 0805 (integrators: must be C0G)",
             "any 0805 C0G 220 pF"),
    "27p": ("C0G/NP0 50 V, 0805", "any 0805 C0G 27 pF"),
    "10u": ("X5R 25 V, 1206", "any 1206 X5R 10 uF 25 V"),
    "2u2": ("film (PET/MKT) 63 V, 10 mm pitch, THT -- input coupling",
            "WIMA MKS4 2.2 uF 63 V"),
    "220u": ("aluminium electrolytic 16 V, SMD 6.3 x 7.7 mm",
             "Panasonic EEE-FK1C221P"),
    "470u": ("aluminium electrolytic 10 V, SMD 8 x 10 mm",
             "Panasonic EEE-FK1A471P"),
}
LEDS = {"RED": "red 0805 LED", "GREEN": "green 0805 LED",
        "YELLOW": "yellow 0805 LED"}
CONN = {
    "LINE IN L": ("2-way screw terminal, 5.08 mm, THT", "bornier-2 5.08"),
    "LINE IN R": ("2-way screw terminal, 5.08 mm, THT", "bornier-2 5.08"),
    "TONEARM GND": ("2-way screw terminal, 5.08 mm, THT", "bornier-2 5.08"),
    "CLK SEL": ("1x3 pin header 2.54 mm + jumper, THT", ""),
    "GND LIFT": ("1x2 pin header 2.54 mm + jumper, THT", ""),
    "WP": ("1x2 pin header 2.54 mm + jumper, THT", ""),
    "TP L": ("2x5 pin header 2.54 mm, THT", ""),
    "TP R": ("2x5 pin header 2.54 mm, THT", ""),
    "TP DIG": ("2x5 pin header 2.54 mm, THT", ""),
}


def comps():
    txt = open(paths.net(NAME), encoding="utf-8").read()
    for blk in re.split(r"\(comp\s*\n", txt)[1:]:
        ref = re.search(r'\(ref "([^"]+)"', blk).group(1)
        val = re.search(r'\(value "([^"]*)"', blk).group(1)
        fp = re.search(r'\(footprint "([^"]*)"', blk).group(1)
        yield ref, val, fp


def describe(ref, val, fp):
    pfx = re.match(r"[A-Z]+", ref).group()
    pkg = fp.split(":")[-1]
    if pfx == "R":
        return "resistor, 1 % thin film, 0805", "any 0805 1 % 0.125 W"
    if pfx == "RV":
        return ("1x3 right-angle header to the panel-mounted 47 k trim pot",
                "")
    if pfx == "C":
        return CAPS.get(val, (pkg, ""))
    if pfx == "L":
        return L10U
    if pfx == "D" and val in LEDS:
        return LEDS[val], "e.g. Kingbright APT2012 series"
    if pfx == "SW":
        return "6 x 6 mm SMD tact switch", "C&K PTS645SM43SMTR92"
    if pfx == "J":
        return CONN.get(val, PARTS.get(val, (pkg, "")))
    return PARTS.get(val, (pkg, ""))


def main():
    groups = collections.defaultdict(list)
    for ref, val, fp in comps():
        spec, pn = describe(ref, val, fp)
        groups[(ref.rstrip("0123456789")[:2], val, spec, pn)].append(ref)
    order = {"R": 0, "RV": 1, "C": 2, "L": 3, "D": 4, "Q": 5, "U": 6, "Y": 7,
             "SW": 8, "J": 9}

    def key(item):
        (pfx, val, _s, _p), _refs = item
        return (order.get(pfx, 5), val)

    total = sum(len(v) for v in groups.values())
    print("# Bill of materials - rev E, the SMD Raspberry Pi HAT")
    print()
    print("Generated by `hardware/kicad/tools/make_bom_smd.py` from "
          "`hardware/kicad/rev_e/vinyl_adc_rev_e.net`. The same circuit as "
          "rev D (`docs/bom-rev-d.md`) in surface-mount parts; the values are "
          "identical, only packages and four part numbers changed "
          "(BC547/557 -> BC847/857, 1N4148 -> 1N4148W, 1N5817 -> SS14, "
          "1N4003 -> S1M). The part numbers are examples of common "
          "catalogue parts: anything meeting the spec column fits.")
    print()
    print(f"{total} components in {len(groups)} lines, one board.")
    print()
    print("| Qty | Value | Refs | Spec | Example |")
    print("|----:|-------|------|------|---------|")
    for (pfx, val, spec, pn), refs in sorted(groups.items(), key=key):
        refs = sorted(refs, key=lambda r: (re.sub(r"\d", "", r),
                                           int(re.sub(r"\D", "", r) or 0)))
        print(f"| {len(refs)} | {val} | {', '.join(refs)} | {spec} | {pn} |")
    print()
    print("## Notes")
    print()
    print("- **C0G where it says C0G.** C22-C24 / C62-C64 are the loop's "
          "integrating capacitors and C21/C61 the input filter; an X7R there "
          "changes value with the voltage across it, which is distortion.")
    print("- **C20 / C60 stay through-hole film.** 2.2 uF does not exist in "
          "C0G, and they sit in series with the audio.")
    print("- The four 10 uF parts are ceramic (X5R, 1206). The flying "
          "capacitor C4 gains from the lower ESR; the timing caps C41-C43 "
          "lose about 40 % to DC bias, so the clip and clock-alive LEDs "
          "hold for ~0.6 s instead of ~1 s.")
    print("- Hardware: four M2.5 x 11 mm standoffs for the Pi, three M3 for "
          "the enclosure; J2 is a plain 8.5 mm 2x20 HAT socket (an 11 mm "
          "extended one if the Pi's PoE header touches the socket).")


if __name__ == "__main__":
    main()
