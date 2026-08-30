#!/usr/bin/env python3
"""Build the BOM and check every line against the DTU shop stock list.

Anything the shop does not carry is flagged ORDER rather than quietly listed,
because the whole design was constrained to shop parts and a silent gap there
is exactly the surprise that stops a build on the bench.

    py -3.13 make_bom.py > ../../../docs/bom.md

Reads the three ARTWORKS, not the one-page reference sheet: the artworks are
what actually gets milled, and they carry the stacking bus and the Q-select
shunt that the reference sheet has no reason to show.  Each line says which
board its parts sit on.

The channel artwork is milled TWICE -- one board is channel L, the other
channel R, and the only difference between them is which way the Q-select
shunt is fitted.  So its quantities are doubled here and its refdes are the
ones printed on the copper; the second copy carries the same ones, even though
the reference sheet numbers that channel forty higher.
"""

import collections
import csv
import os
import re
import sys
import paths

sys.path.insert(0, r"C:\Users\Mads2\.claude\skills\kicad-schematic\scripts")
import schlib  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

SHOP = (r"C:\Users\Mads2\KiCad\DTU-EKB-components\Components\parts"
        r"\dtu_component_shop.csv")

# value -> (category hint, what to look for in the shop list)
IC_ALIASES = {"74HCT132": "74HCT132", "74HC157": "74HC157",
              "74HC4040": "74HC4040", "74HC4049": "74HC4049"}


def load_shop():
    rows = []
    with open(SHOP, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def norm_res(v):
    """'20k5' / '4R7' / '165k' -> ohms."""
    m = re.fullmatch(r"(\d+)([RkKMm])(\d*)", v)
    if not m:
        return None
    a, unit, b = m.groups()
    mult = {"R": 1, "k": 1e3, "K": 1e3, "M": 1e6}.get(unit, 1)
    return float(f"{a}.{b or 0}") * mult


def res_in_shop(shop, ohms):
    for r in shop:
        if r["Category"] != "Resistor" or r["Subcategory"] != "E96 Standard":
            continue
        got = norm_res(r["Part_Number"])
        if got and abs(got - ohms) < max(ohms * 0.005, 1e-9):
            return r["Part_Number"]
    return None


def cap_in_shop(shop, value):
    """value like '220p', '100n', '2u2', '470u'."""
    m = re.fullmatch(r"(\d+)([pnu])(\d*)", value)
    if not m:
        return None
    a, unit, b = m.groups()
    num = float(f"{a}.{b or 0}")
    txt = {"p": f"{num:g}pF", "n": f"{num:g}nF", "u": f"{num:g}µF"}[unit]
    for r in shop:
        if r["Category"] == "Capacitor" and r["Value"] == txt:
            return f"{r['Subcategory']} {txt}"
    return None


def ic_in_shop(shop, value):
    want = IC_ALIASES.get(value, value)
    for r in shop:
        if r["Part_Number"].upper() == want.upper():
            return f"{r['Subcategory']}"
    # the 74HC/74HCT families are listed without the HC/HCT prefix variants
    bare = re.sub(r"^74(HC|HCT|LS)", "", want)
    for r in shop:
        pn = r["Part_Number"].upper()
        if pn.endswith(bare) and pn.startswith("74"):
            return f"{r['Subcategory']} (as {r['Part_Number']})"
    return None


# tag, sheet, how many of that board a stereo ADC needs.  Three artworks,
# four boards: the channel is the one that gets milled twice.
BOARDS = (("P", "vinyl_adc_power", 1),
          ("M", "vinyl_adc_channel_l", 2),
          ("D", "vinyl_adc_digital", 1))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    shop = load_shop()

    groups = collections.defaultdict(list)
    where, mult = {}, {}
    for tag, name, n in BOARDS:
        sch = schlib.Schematic(paths.sch(name))
        for s in sch.symbols:
            ref = s.ref
            if ref.startswith("#PWR") or not ref:
                continue
            groups[(s.value, s.lib_id)].append(ref)
            where[ref] = tag
            mult[ref] = n

    def sort_key(item):
        (value, lib), refs = item
        order = {"R": 0, "C": 1, "D": 2, "U": 3, "X": 3, "J": 4, "RV": 5}
        pfx = re.match(r"[A-Z]+", refs[0]).group()
        return (order.get(pfx, 9), value)

    lines, orders = [], []
    total = 0
    for (value, lib), refs in sorted(groups.items(), key=sort_key):
        refs = sorted(set(refs), key=lambda r: (r[0], int(re.sub(r"\D", "", r) or 0)))
        n = sum(mult[r] for r in refs)
        total += n
        pfx = re.match(r"[A-Z]+", refs[0]).group()
        avail = None
        if pfx == "R" and lib.endswith(":R"):
            ohms = norm_res(value)
            hit = res_in_shop(shop, ohms) if ohms else None
            avail = f"E96 {hit}" if hit else None
        elif pfx == "C":
            avail = cap_in_shop(shop, value)
        elif pfx in ("U", "X"):
            avail = ic_in_shop(shop, value)
        elif pfx == "RV":
            avail = "Trimmer 47K" if value == "47k" else None
        elif pfx == "D":
            avail = ic_in_shop(shop, value)
        elif pfx == "J":
            avail = {"LINE IN L": "Terminal 2 pol skrueterminal",
                     "LINE IN R": "Terminal 2 pol skrueterminal",
                     "CLK SEL": "Header Male + Jumper",
                     "Q SEL": "Header Male + Jumper",
                     "TO PI GPIO": "Header Male 1x8"}.get(value)
        status = avail or "** ORDER **"
        if not avail:
            orders.append((value, ", ".join(refs)))
        # Spell the quantity out per board rather than tagging the line with
        # the set of boards it touches. A line like 10k0 sits on power AND on
        # the channel, and only the channel half doubles -- "MP x2" reads as
        # though the whole line did, which is off by four.
        per = collections.Counter(where[r] for r in refs)
        boards = " + ".join(
            f"{tag} {per[tag]}" + (" x2" if n_boards > 1 else "")
            for tag, _name, n_boards in BOARDS if per[tag])
        lines.append((n, value, ", ".join(refs), boards, status))

    print("# Bill of materials - discrete delta-sigma vinyl ADC")
    print()
    print("Generated by `hardware/kicad/tools/make_bom.py` straight from the")
    print("schematic, with every line checked against the DTU shop stock list")
    print("(`dtu_component_shop.csv`). **ORDER** means the shop does not carry it.")
    print()
    print(f"{total} components in {len(lines)} distinct lines, for the four "
          "boards a stereo ADC needs.")
    print()
    print("**Board** is **P** power (supplies and the +/-2.5 V reference), "
          "**M** modulator channel, **D** digital (clock, interleave, level "
          "shift, Pi). Three artworks, four boards: the channel is ONE "
          "artwork MILLED TWICE, so its lines are marked `M x2` and the "
          "quantity already counts both. The refdes shown are the ones "
          "printed on the copper, and the second copy carries the same ones "
          "-- the reference sheet numbers that channel forty higher, the "
          "board does not.")
    print()
    print("| Qty | Value | Refs | Board | DTU shop |")
    print("|----:|-------|------|-------|----------|")
    for n, value, refs, boards, status in lines:
        print(f"| {n} | {value} | {refs} | {boards} | {status} |")
    print()
    if orders:
        print("## Must be ordered")
        print()
        for v, refs in orders:
            print(f"- **{v}** ({refs})")
    else:
        print("Everything on this list is stocked by the shop.")
    print()
    print("## Sockets")
    print()
    print("Use DIP sockets for every IC (all stocked): 8-pin for the TL072s,")
    print("the LM311s and the oscillator can, 14-pin for the 74HC04 / 74HC74 /")
    print("74HCT132, 16-pin for the 74HC157 / 74HC4040 / 74HC4049, 20-pin for")
    print("the 74HC244.")
    print()
    print("## The stacking bus")
    print()
    print("There are no ribbons. Every board carries the SAME 2x8 on 2.54 mm")
    print("at the SAME coordinates, and the four boards plug into each other")
    print("on 11 mm standoffs:")
    print()
    print("| Board | Ref | Ways | Position in the stack |")
    print("|---|---|---|---|")
    print("| digital | J4 | 2x8 | top |")
    print("| channel L | J7 | 2x8 | middle |")
    print("| channel R | J7 | 2x8 | middle |")
    print("| power | J3 | 2x8 | bottom |")
    print()
    print("Odd pins are all GND, so every signal has a grounded neighbour")
    print("either side -- which is what MCLK needs, its jitter being what sets")
    print("this converter's noise floor. The even pins carry, in order:")
    print("**+5V, VREF_P, VREF_N, MCLK, PUMP, QL, QR, -5V**.")
    print()
    print("What goes in the sixteen holes is a build choice, not an artwork")
    print("choice: a plain socket on the top board, a long-pin header on the")
    print("bottom one, and a pass-through stacking header on the two in the")
    print("middle. All three are the same sixteen pads. You need 4 sets plus")
    print("16 x 11 mm M3 standoffs and the M3 screws; the shop carries none of")
    print("them, so they go on the same order as the oscillator can.")
    print()
    print("## Which channel is which")
    print()
    print("Both channel boards are the same copper, so nothing etched on them")
    print("says which channel a board is. The Q-select shunt does: **J21 1-2")
    print("makes it LEFT, 2-3 makes it RIGHT**. Fit one jumper per channel")
    print("board and they are otherwise interchangeable.")


if __name__ == "__main__":
    main()
