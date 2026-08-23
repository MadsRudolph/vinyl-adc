#!/usr/bin/env python3
"""Where each functional block landed on the board, and whether it stayed one block.

    py -3.13 tools/pcb_blocks.py ../vinyl_adc_common.kicad_pcb

An auto-placer optimises half-perimeter wire length; it has no idea that this is
a delta-sigma ADC whose two analog channels want to stay away from the digital
section and from each other. This says what actually happened: the bounding box
of every block, how far apart they ended up, and which blocks overlap.
Blocks whose parts are not on the board given are simply absent, so the same
list serves all three designs.

Overlap is not automatically wrong -- a 17 % utilisation board has room to
interleave and the router may well prefer it -- but on this design an analog
channel sharing a rectangle with the clock divider is worth knowing about before
the copper is cut.
"""
import re
import sys
from pathlib import Path

BLOCKS = {
    "power in + charge pump": ["C1", "C2", "C3", "C4", "C5", "C6", "D1", "D2",
                               "R1", "U1"],
    "+/-2.5 V reference": ["R2", "R3", "R4", "R5", "C7", "C8", "U2"],
    "clock + divider": ["X1", "J1", "U3", "U4", "C9", "C10", "C11"],
    "quantiser": ["U5", "C12"],
    "DAC gates": ["U7", "C14"],
    "interleave": ["U6", "C13"],
    "level shift + Pi": ["U8", "C15", "J2"],
    # one entry per connector, not one for all of them: three ribbons spread
    # across a band share a bounding box the size of the band, and the report
    # then claims every other block overlaps it
    "link to digital": ["J3", "J4"],
    "link to channel L": ["J5"],
    "link to channel R": ["J6"],
    "link to common": ["J7"],
    "channel L": ["J20", "C20", "C21", "RV20", "U20", "U21"]
                 + [f"R{n}" for n in range(20, 38)]
                 + [f"C{n}" for n in range(22, 28)],
    "channel R": ["J60", "C60", "C61", "RV60", "U60", "U61"]
                 + [f"R{n}" for n in range(60, 78)]
                 + [f"C{n}" for n in range(62, 68)],
}


def positions(path):
    """{ref: (x, y)} for every footprint on the board.

    Anything between the library id and the position is skipped rather than
    matched: a LOCKED footprint carries `(locked yes)` there, and a pattern
    that insists on `(layer ...)` coming next silently drops exactly the parts
    that were placed by hand -- which is every part you most wanted to check.
    """
    t = Path(path).read_text(encoding="utf-8", errors="replace")
    out = {}
    for m in re.finditer(
            r'\(footprint "[^"]+".*?'
            r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\).*?'
            r'\(property "Reference" "([^"]+)"', t, re.S):
        out[m.group(4)] = (float(m.group(1)), float(m.group(2)))
    return out


def bbox(refs, pos):
    pts = [pos[r] for r in refs if r in pos]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys), len(pts)


def overlap(a, b):
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[1], b[1])
    return ox > 0 and oy > 0, max(0.0, ox), max(0.0, oy)


def main(path):
    pos = positions(path)
    print(f"{len(pos)} footprints in {Path(path).name}\n")
    boxes = {}
    print(f"{'block':24s} {'n':>3s}  {'x range':>15s}  {'y range':>15s}  "
          f"{'span mm':>13s}")
    for name, refs in BLOCKS.items():
        bb = bbox(refs, pos)
        if not bb:
            continue
        x0, y0, x1, y1, n = bb
        boxes[name] = (x0, y0, x1, y1)
        print(f"{name:24s} {n:3d}  {x0:6.1f}..{x1:6.1f}  {y0:6.1f}..{y1:6.1f}  "
              f"{x1-x0:5.1f} x {y1-y0:5.1f}")
    placed = sum(len(bbox(r, pos) and [1] * bbox(r, pos)[4] or [])
                 for r in BLOCKS.values())
    missing = sorted(set(pos) - {r for refs in BLOCKS.values() for r in refs})
    if missing:
        print(f"\nnot in any block: {' '.join(missing)}")

    print("\noverlapping blocks (bounding boxes):")
    names = list(boxes)
    any_ov = False
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ov, ox, oy = overlap(boxes[names[i]], boxes[names[j]])
            if ov:
                any_ov = True
                print(f"   {names[i]:24s} x {names[j]:24s}  "
                      f"{ox:5.1f} x {oy:5.1f} mm")
    if not any_ov:
        print("   none -- every block occupies its own rectangle")

    if "channel L" in boxes and "channel R" in boxes:
        l, r = boxes["channel L"], boxes["channel R"]
        cl = ((l[0] + l[2]) / 2, (l[1] + l[3]) / 2)
        cr = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
        d = ((cl[0] - cr[0]) ** 2 + (cl[1] - cr[1]) ** 2) ** 0.5
        print(f"\nchannel L to channel R, centre to centre: {d:.0f} mm")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../vinyl_adc.kicad_pcb")
