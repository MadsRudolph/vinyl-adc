#!/usr/bin/env python3
"""What is still unrouted on each board, as pad-to-pad links you can solder.

    py -3.13 tools/remaining_links.py [board ...]

`place_route.py check` tells you a net is in three pieces; that is the right
number to judge a board by, but it is not the thing you act on at the bench.
This prints the individual links KiCad's own DRC says are missing, each with
both endpoints and their coordinates, grouped by net -- so you can work down
the list and re-run it as the list shrinks.

Read it against `place_route.py check`, not instead of it.  DRC's unconnected
count and union-find's `sum(pieces - 1)` agree on every board here, and if they
ever stop agreeing believe neither until you know why.

The endpoints DRC reports are whatever it found nearest the gap, so one end is
sometimes a TRACK rather than a pad -- "join this pad to that track" is still
the link, but the track end is a point on existing copper, not a hole.  Where
both ends are pads, the link is hole-to-hole and a wire on the component side
does it.
"""

import collections
import json
import os
import subprocess
import sys
import tempfile
import paths

KICAD = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"

# DRC violations that are the documented exception on this process, not faults.
# The .kicad_dru files already suppress the intra-footprint clearance hits; what
# is left over is listed so you can see it rather than having it hidden.
BENIGN = {"silk_overlap", "silk_edge_clearance", "starved_thermal"}


def drc(pcb):
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "drc.json")
        subprocess.run([KICAD, "pcb", "drc", "--format", "json",
                        "--severity-error", "--severity-warning",
                        "-o", out, pcb], check=True, capture_output=True)
        with open(out, encoding="utf-8") as f:
            return json.load(f)


def endpoint(item):
    pos = item.get("pos") or {}
    return "%s @(%.2f, %.2f)" % (item.get("description", "?"),
                                 pos.get("x", 0.0), pos.get("y", 0.0))


def net_of(item):
    """`PTH pad 12 [QL] of J4` / `Track [QL] on B.Cu, ...` -> QL."""
    d = item.get("description", "")
    a, b = d.find("["), d.find("]")
    return d[a + 1:b] if 0 <= a < b else "?"


def main(argv):
    names = argv[1:] or list(paths.BOARDS)
    rc = 0
    for name in names:
        pcb = paths.pcb(name)
        if not os.path.exists(pcb):
            print(f"{name}: no board on disk ({pcb})")
            continue
        d = drc(pcb)
        unc = d.get("unconnected_items", [])
        viol = d.get("violations", [])
        real = [v for v in viol if v["type"] not in BENIGN]
        benign = [v for v in viol if v["type"] in BENIGN]

        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        if not unc:
            print("  0 links left -- every net is in one piece")
        else:
            by_net = collections.defaultdict(list)
            for u in unc:
                items = u.get("items", [])
                by_net[net_of(items[0]) if items else "?"].append(items)
            print(f"  {len(unc)} link(s) left over {len(by_net)} net(s):")
            for net in sorted(by_net):
                print(f"    {net}")
                for items in by_net[net]:
                    print("      " + "\n        to ".join(
                        endpoint(i) for i in items))
        if real:
            print("  DRC still reports, and these are NOT the documented "
                  "exception:")
            for t, n in sorted(collections.Counter(
                    v["type"] for v in real).items()):
                print(f"    {t}: {n}")
            rc = 1
        if benign:
            print("  benign/cosmetic: " + ", ".join(
                f"{t} {n}" for t, n in sorted(collections.Counter(
                    v["type"] for v in benign).items())))
        if unc:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
