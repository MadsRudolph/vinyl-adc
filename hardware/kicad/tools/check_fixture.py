#!/usr/bin/env python
r"""Prove the three artworks still agree well enough to stack.

    & "C:\Program Files\KiCad\10.0\bin\python.exe" tools\check_fixture.py

The boards plug into one another, so three things have to be identical on all
of them and nothing in the layout flow enforces it: the outline, the four M3
standoff holes, and the bus.  Nudge the bus 2.54 mm on one board while
placing parts and every other check still passes -- the netlist is untouched,
DRC is clean, the sheet is fine -- and the stack simply will not go together.
Worse, a HALF-pitch nudge lets it go together one row out, which is +5V onto
a ground column.

The bus test is on pad POSITION AND PIN NUMBER, not on the footprint's
origin: a connector rotated 180 degrees about its own centre keeps its origin
and reverses its pins, which is exactly the failure that would be invisible.
"""
import os
import sys
import paths

import pcbnew
from pcbnew import ToMM

BOARDS = (("vinyl_adc_power", "J3"),
          ("vinyl_adc_channel_l", "J7"),
          ("vinyl_adc_digital", "J4"))


def survey(path, bus_ref):
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    outline = (round(ToMM(bb.GetLeft()), 2), round(ToMM(bb.GetTop()), 2),
               round(ToMM(bb.GetWidth()), 2), round(ToMM(bb.GetHeight()), 2))
    holes, unlocked, bus, bus_locked = [], [], None, False
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith("H") and ref[1:].isdigit():
            holes.append((round(ToMM(fp.GetX()), 2), round(ToMM(fp.GetY()), 2)))
            if not fp.IsLocked():
                unlocked.append(ref)
        if ref == bus_ref:
            bus = sorted((p.GetNumber(), round(ToMM(p.GetX()), 3),
                          round(ToMM(p.GetY()), 3)) for p in fp.Pads())
            bus_locked = fp.IsLocked()
            if not bus_locked:
                unlocked.append(ref)
    return outline, sorted(holes), bus, unlocked


def main():
    rows, faults = [], []
    for name, ref in BOARDS:
        p = paths.pcb(name)
        if not os.path.exists(p):
            faults.append(f"{name}: no board file")
            continue
        outline, holes, bus, unlocked = survey(p, ref)
        if bus is None:
            faults.append(f"{name}: bus connector {ref} not on the board")
        if len(holes) != 4:
            faults.append(f"{name}: {len(holes)} M3 holes, expected 4")
        for u in unlocked:
            faults.append(f"{name}: {u} is not locked")
        rows.append((name, outline, holes, bus))
        print(f"{name:24s} outline={outline}  holes={len(holes)}  "
              f"bus_pads={len(bus) if bus else 0}")

    for label, idx in (("outline", 1), ("M3 holes", 2), ("bus pads+pins", 3)):
        vals = [r[idx] for r in rows]
        if not all(v == vals[0] for v in vals):
            faults.append(f"{label} differ between boards -- the stack will "
                          f"not mate")
            for r in rows:
                print(f"    {r[0]:24s} {label} = {r[idx]}")

    print()
    if faults:
        print(f"FAIL  {len(faults)} fixture fault(s):")
        for f in faults:
            print("   -", f)
        return 1
    print("PASS  all three artworks share one outline, one hole pattern "
          "and one bus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
