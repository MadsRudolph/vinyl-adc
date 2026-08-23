#!/usr/bin/env python3
"""What the router actually produced: copper by layer, and the wire bridges.

    py -3.13 tools/pcb_report.py ../vinyl_adc.kicad_pcb

On a single-sided board every F.Cu track is a wire you will have to solder by
hand, so it is counted here and never rolled into a "routed %". The B.Cu total
is the copper the mill has to isolate.

Note KiCad 10 writes a track's net as a NAME -- `(net "+5V")` -- not as the
numeric index older files used. A pattern written for the old form matches
nothing at all and reports a fully routed board as having no copper.
"""
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SEG = re.compile(
    r'\(segment\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)'
    r'\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)\s*\(net "([^"]*)"\)', re.S)


def runs(segs):
    """Group segments into connected runs -- one run is one wire to solder."""
    pts = defaultdict(list)
    for i, s in enumerate(segs):
        pts[(round(float(s[0]), 3), round(float(s[1]), 3))].append(i)
        pts[(round(float(s[2]), 3), round(float(s[3]), 3))].append(i)
    parent = list(range(len(segs)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for group in pts.values():
        for b in group[1:]:
            ra, rb = find(group[0]), find(b)
            if ra != rb:
                parent[rb] = ra
    return Counter(find(i) for i in range(len(segs)))


def main(path):
    t = Path(path).read_text(encoding="utf-8", errors="replace")
    segs = SEG.findall(t)
    n_fp = len(re.findall(r"\(footprint ", t))
    vias = re.findall(r'\(via\s*\(at [-\d. ]+\)\s*\(size [\d.]+\)'
                      r'\s*\(drill [\d.]+\)\s*\(layers[^)]*\)\s*\(net "([^"]*)"\)',
                      t, re.S)

    by_layer = Counter()
    length = Counter()
    for x1, y1, x2, y2, w, layer, net in segs:
        by_layer[layer] += 1
        length[layer] += math.hypot(float(x2) - float(x1), float(y2) - float(y1))

    print(Path(path).name)
    print(f"  {n_fp} footprints, {len(segs)} track segments, {len(vias)} vias")
    for layer in sorted(by_layer):
        print(f"    {layer:6s} {by_layer[layer]:4d} segments, "
              f"{length[layer]:7.0f} mm")

    top = [s for s in segs if s[5] == "F.Cu"]
    if top:
        r = runs(top)
        print(f"\n  F.Cu copper is not copper on a single-sided board -- it is "
              f"{len(r)} wire bridges to solder ({len(top)} segments).")
        per_net = Counter(s[6] for s in top)
        for name, n in per_net.most_common(12):
            print(f"    {name:22s} {n:3d} segments")
    else:
        print("\n  no F.Cu copper: nothing to bridge by hand")

    if vias:
        print(f"\n  {len(vias)} vias -- on a single-sided board each one is a "
              f"hole to rivet or wire through:")
        for name, n in Counter(vias).most_common(8):
            print(f"    {name:22s} {n:3d}")

    print("\n  track widths: "
          + ", ".join(f"{w} mm x{n}"
                      for w, n in sorted(Counter(s[4] for s in segs).items())))
    print("  drill sizes : "
          + ", ".join(f"{d} mm x{n}" for d, n in
                      sorted(Counter(re.findall(r'\(drill ([\d.]+)\)', t)).items())))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../vinyl_adc.kicad_pcb")
