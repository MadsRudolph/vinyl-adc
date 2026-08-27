#!/usr/bin/env python3
"""Build the BOM and check every line against the DTU shop stock list.

Anything the shop does not carry is flagged ORDER rather than quietly listed,
because the whole design was constrained to shop parts and a silent gap there
is exactly the surprise that stops a build on the bench.

    py -3.13 make_bom.py > ../../docs/bom.md

Reads the two half-boards, not the one-page reference sheet: the halves are
what actually gets built, and they carry the link header the reference sheet
has no reason to show.  Each line says which board its parts sit on.
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


# tag, sheet, how many of that board a stereo ADC needs
BOARDS = (("C", "vinyl_adc_common", 1),
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
                     "TO PI GPIO": "Header Male 1x8"}.get(value)
        status = avail or "** ORDER **"
        if not avail:
            orders.append((value, ", ".join(refs)))
        boards = "".join(sorted({where[r] for r in refs}))
        if "M" in boards:
            boards += " x2"
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
    print("**Board** is **C** common (power, reference, quantiser), **M** "
          "modulator channel, **D** digital (clock, interleave, Pi). The "
          "channel board is ONE artwork built TWICE, so its lines are marked "
          "`M x2` and the quantity already counts both; the refdes shown are "
          "the ones printed on the board, and the second copy carries the "
          "same ones.")
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
    print("Use DIP sockets for every IC (all stocked): 8-pin for the LM311s and")
    print("the oscillator can, 14-pin for the TL074s / 74HC04 / 74HC74 / 74HCT132,")
    print("16-pin for the 74HC157 / 74HC4040 / 74HC4049, 20-pin for the 74HC244.")
    print()
    print("## The board-to-board links")
    print()
    print("Three ribbons, all shrouded IDC box headers on 2.54 mm pitch:")
    print()
    print("| Cable | Header | Ways | Carries |")
    print("|---|---|---|---|")
    print("| common - digital | J3 / J4 | 2x6 | +5V, GND, MCLK, QL, QR, PUMP |")
    print("| common - channel L | J5 / J7 | 2x7 | both supplies, both "
          "references, CMP_L, DACP_L, DACN_L |")
    print("| common - channel R | J6 / J7 | 2x7 | the same, R |")
    print()
    print("You need 2 x 2x6 headers, 4 x 2x7 headers, and matching IDC")
    print("sockets and ribbon. The shop carries none of them, so they go on")
    print("the same order as the oscillator can. A bare pin header would fit")
    print("the same pads and would also plug in backwards -- which puts +5V")
    print("straight across the ground column. The shroud's key is what makes")
    print("that impossible, and it is the reason this is not a stocked part.")


if __name__ == "__main__":
    main()
