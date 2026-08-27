#!/usr/bin/env python
r"""Stamp the geometry the three artworks MUST agree on, or the stack won't mate.

    & "C:\Program Files\KiCad\10.0\bin\python.exe" tools\pcb_fixture.py
    & "C:\Program Files\KiCad\10.0\bin\python.exe" tools\pcb_fixture.py vinyl_adc_power

Outline, the four M3 standoff holes and the stacking bus -- and nothing else.
Placement, routing and pours are the board author's job; this script never
touches them.  It picks its board from the file name, so there is one fixture
script and not three.

Everything here is deliberately IDENTICAL on all three boards.  The boards
plug into each other, so pin 1 of one has to sit directly above pin 1 of the
next; `check_fixture.py` is the gate that proves it still does.

ONE BUS POSITION, not a socket and a header side by side.  A middle board has
to present a socket UPWARDS to the board above and pins DOWNWARDS to the board
below, and stacking identical boards puts one directly over the other -- so
both must share an XY, which two separate parts cannot do.  What goes in the
holes is a build choice: a plain socket on the top board, a long-pin header on
the bottom one, a pass-through stacking header on the two in the middle.  All
three are the same sixteen pads on 2.54 mm, so the artwork does not care.

REMOVAL IS DONE AS TEXT, and that is not fussiness.  `board.Remove()` on a
PCB_SHAPE segfaults the SWIG runtime part way through deleting the four
Edge.Cuts segments and takes the interpreter with it -- so the save-and-reload
dance that rescues `pcb_pours.py` from the same bug on ZONEs does not help
here, because execution never reaches the save.  It only bites on the SECOND
run, when there is finally something to remove, which is exactly when you have
stopped expecting it.  So: strip the old geometry out of the s-expression as
text, then let pcbnew do only what it is reliable at, which is adding.
"""
import io
import os
import re
import sys
import paths

import pcbnew
from pcbnew import VECTOR2I, FromMM, EDA_ANGLE, DEGREES_T

# --- the fixture ------------------------------------------------------------
X0, Y0, W, H = 20.0, 20.0, 100.0, 100.0   # outline, in absolute board coords
INSET = 6.0                               # M3 centres, in from each edge
BUS_AT = (X0 + W / 2, Y0 + 10.0)          # on the centreline, along the top
# 270, not 90: the odd pins are all GND and the even pins are every signal, so
# the two rows are not interchangeable.  At 90 the signal row faced the board
# EDGE, and all eight had to climb around the connector before they could go
# anywhere.  At 270 the ground row takes the edge -- where it wants to be, next
# to the pour -- and the signals open straight into the board.
#
# This also REVERSES the pin order about the connector's centre, which is only
# safe because all three boards rotate together.  check_fixture.py tests pad
# position AND pin number for exactly this reason: a board left at 90 would
# still bolt up and would put +5V on the ground column.
BUS_ROT = 270.0

MH_LIB = r"C:\Program Files\KiCad\10.0\share\kicad\footprints\MountingHole.pretty"
MH_FP = "MountingHole_3.2mm_M3"

# Which connector is the bus differs per board only because the refdes do.
BUS_REF = {
    "vinyl_adc_power": "J3",
    "vinyl_adc_channel_l": "J7",
    "vinyl_adc_channel_r": "J7",
    "vinyl_adc_digital": "J4",
}

BS = chr(92)


# --- pass one: strip, as text ----------------------------------------------

def _blocks(s, head):
    """Every `(head ...)` block in `s`, as (start, end).  Quote-aware."""
    out, i = [], 0
    while True:
        i = s.find("(" + head, i)
        if i < 0:
            return out
        depth, j, in_str = 0, i, False
        while j < len(s):
            c = s[j]
            if in_str:
                if c == BS:
                    j += 2
                    continue
                if c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    out.append((i, j + 1))
                    break
            j += 1
        i = j + 1


def _drop(s, head, keep_out):
    cuts = [(a, b) for a, b in _blocks(s, head) if keep_out(s[a:b])]
    for a, b in reversed(cuts):
        s = s[:a] + s[b:]
    return s, len(cuts)


def strip(path):
    """Take the previous outline and M3 holes back out, so re-runs are safe."""
    s = io.open(path, encoding="utf-8").read()
    shapes = 0
    for head in ("gr_line", "gr_rect", "gr_arc", "gr_poly", "gr_circle"):
        s, k = _drop(s, head, lambda t: '"Edge.Cuts"' in t)
        shapes += k
    s, holes = _drop(
        s, "footprint",
        lambda t: re.search(r'\(property "Reference" "H[0-9]+"', t) is not None)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    return shapes, holes


# --- pass two: add, with pcbnew --------------------------------------------

def add(path, bus_ref):
    b = pcbnew.LoadBoard(path)

    corners = ((X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H))
    for k in range(4):
        a, c = corners[k], corners[(k + 1) % 4]
        seg = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1])))
        seg.SetEnd(VECTOR2I(FromMM(c[0]), FromMM(c[1])))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(FromMM(0.1))
        b.Add(seg)

    holes = []
    for i, (dx, dy) in enumerate(((INSET, INSET), (W - INSET, INSET),
                                  (INSET, H - INSET), (W - INSET, H - INSET))):
        fp = pcbnew.FootprintLoad(MH_LIB, MH_FP)
        if fp is None:
            raise SystemExit(f"could not load {MH_FP} from {MH_LIB}")
        fp.SetReference("H%d" % (i + 1))
        fp.SetPosition(VECTOR2I(FromMM(X0 + dx), FromMM(Y0 + dy)))
        fp.SetLocked(True)
        b.Add(fp)
        holes.append((X0 + dx, Y0 + dy))

    found = False
    for fp in b.GetFootprints():
        if fp.GetReference() == bus_ref:
            fp.SetPosition(VECTOR2I(FromMM(BUS_AT[0]), FromMM(BUS_AT[1])))
            fp.SetOrientation(EDA_ANGLE(BUS_ROT, DEGREES_T))
            # Then correct by the PADS, not the origin.  A 2x08 header's
            # origin is pin 1, not its centre, so setting the origin to the
            # board centreline leaves the connector half its own length off
            # to one side -- 8.89 mm here, which is neither symmetric nor
            # what the M3 pattern implies.  Measure the pad extent and shift.
            xs = [q.GetX() for q in fp.Pads()]
            ys = [q.GetY() for q in fp.Pads()]
            dx = FromMM(BUS_AT[0]) - (min(xs) + max(xs)) // 2
            dy = FromMM(BUS_AT[1]) - min(ys)   # near-edge row lands on BUS_AT
            fp.Move(VECTOR2I(dx, dy))
            fp.SetLocked(True)
            found = True
    if not found:
        raise SystemExit(f"bus connector {bus_ref} not found in {path}")

    pcbnew.SaveBoard(path, b)
    return holes


def one(path):
    name = os.path.splitext(os.path.basename(path))[0]
    ref = BUS_REF.get(name)
    if ref is None:
        raise SystemExit(f"no bus refdes known for {name}")
    shapes, old = strip(path)
    holes = add(path, ref)
    print(f"{name}: {W:.0f}x{H:.0f} at ({X0:.0f},{Y0:.0f})  "
          f"M3 {holes}  {ref} locked at {BUS_AT} rot {BUS_ROT:.0f}  "
          f"(stripped {shapes} shape(s), {old} hole(s))")


if __name__ == "__main__":
    for a in (sys.argv[1:] or paths.BOARDS):
        one(a if a.endswith(".kicad_pcb") else paths.pcb(a))
