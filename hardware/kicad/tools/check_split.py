#!/usr/bin/env python3
"""Gate: the four milled boards, joined by their ribbons, ARE the reference sheet.

    py -3.13 tools/check_split.py

`vinyl_adc.kicad_sch` is the whole converter on one page.  It is the sheet the
testbenches link back to and the one `check_intent.py` reads, and it is never
milled.  What gets cut is four boards from three designs:

    vinyl_adc_common      power, the +/-2.5 V reference, the quantiser
    vinyl_adc_digital     the clock, the interleave mux, the level shift, the Pi
    vinyl_adc_channel_l   one modulator channel  ) THE SAME ARTWORK,
    vinyl_adc_channel_r   the other              ) built twice

Nothing else enforces that those still add up to it.  They all come out of one
layout script and share block functions, but sharing a *drawing* is not sharing
*connectivity*: a block called from the wrong composer, a label misspelt at one
end of a cable, a net that quietly ends up crossing without a pin to cross on
-- every one of those leaves score, ERC, geometry and footprint checks
perfectly green on all five files, because each file is individually
consistent.  The fault only exists in the relationship between them.

So this welds each link's pin *n* to its partner's pin *n*, drops the
connectors, and requires the resulting partition of every (ref, pin) node to be
IDENTICAL to the reference sheet's.  A part that moved to another board is
invisible here, and should be -- that is the whole point of splitting.  A part
that was lost, doubled, or left connected to something it should not be, is not.

It also proves the two channel boards are ONE artwork: channel R's netlist must
be channel L's with every refdes number raised by forty.  If that ever stops
being true, the second board is a second design and nobody has noticed.
"""

import os
import re
import sys
from collections import defaultdict
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from check_intent import load, netof                          # noqa: E402
from vinyl_adc_layout import LINK_DIGITAL, link_channel       # noqa: E402

REF = "vinyl_adc"
COMMON, DIGITAL = "vinyl_adc_common", "vinyl_adc_digital"
CH_L, CH_R = "vinyl_adc_channel_l", "vinyl_adc_channel_r"
BOARDS = (COMMON, DIGITAL, CH_L, CH_R)

# (board A, its connector) <-> (board B, its connector), and the pinout both
# ends must agree on
LINKS = (
    (COMMON, "J3", DIGITAL, "J4", LINK_DIGITAL),
    (COMMON, "J5", CH_L, "J7", link_channel("L")),
    (COMMON, "J6", CH_R, "J7", link_channel("R")),
)
LINK_REFS = {"J3", "J4", "J5", "J6", "J7"}

# channel R is channel L with every refdes forty higher
CHANNEL_OFFSET = 40


def netlist(name):
    """The netlist KiCad exports, refreshed if the sheet is newer."""
    return load(paths.net(name), paths.sch(name))


class Union:
    def __init__(self):
        self.parent = {}

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def describe(group):
    return " ".join(sorted(f"{r}.{p}" for r, p in group))


def bump(ref, by=CHANNEL_OFFSET):
    """R20 -> R60, C24 -> C64; a link connector keeps its own number."""
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", ref)
    if not m or ref in LINK_REFS:
        return ref
    return f"{m.group(1)}{int(m.group(2)) + by}"


def check_one_artwork(nets_l, nets_r, fail):
    """Channel R must be channel L with every refdes number raised by forty."""
    def part(nets, remap):
        out = set()
        for nodes in nets.values():
            g = frozenset((remap(r), p) for r, p in nodes
                          if not r.startswith("#"))
            if g:
                out.add(g)
        return out

    want = part(nets_l, bump)
    got = part(nets_r, lambda r: r)
    for g in sorted(want - got, key=describe):
        fail.append("channel R is missing what channel L has at "
                    + describe(g))
    for g in sorted(got - want, key=describe):
        fail.append("channel R has a connection channel L does not: "
                    + describe(g))
    if want == got:
        print(f"  the two channel boards are one artwork "
              f"({len(want)} nets, refdes +{CHANNEL_OFFSET})")


def main():
    fail = []
    ref = netlist(REF)
    nets = {name: netlist(name) for name in BOARDS}
    print(f"reference {REF}: {len(ref)} nets")
    for name in BOARDS:
        print(f"  {name}: {len(nets[name])} nets")
    print()
    check_one_artwork(nets[CH_L], nets[CH_R], fail)

    # -- no refdes may exist on two boards, connectors excepted --------------
    # If one did, a part would be built twice and counted once, and the
    # comparison below would be meaningless rather than wrong. The channel
    # boards share J7 by design: they are the same artwork.
    seen = defaultdict(set)
    for name in BOARDS:
        for nodes in nets[name].values():
            for r, _ in nodes:
                if not r.startswith("#") and r not in LINK_REFS:
                    seen[r].add(name)
    for r, where in sorted(seen.items()):
        if len(where) > 1:
            fail.append(f"{r} is on {' and '.join(sorted(where))}")

    # -- weld the ribbons ---------------------------------------------------
    u = Union()
    for name in BOARDS:
        for nodes in nets[name].values():
            nodes = sorted((name,) + n for n in nodes)
            for n in nodes:
                u.find(n)           # register even a one-node net: an NC pin
                u.join(nodes[0], n)  # is still a net the reference has
    for ba, ja, bb, jb, pins in LINKS:
        for pin, net, _kind in pins:
            ends = {ba: netof(nets[ba], ja, str(pin)),
                    bb: netof(nets[bb], jb, str(pin))}
            if None in ends.values():
                fail.append(f"{ja}/{jb} pin {pin} is on no net at all")
            elif len(set(ends.values())) != 1 or ends[ba] != net:
                fail.append(f"{ja}.{pin}/{jb}.{pin} should be {net} at both "
                            "ends, " + ", ".join(f"{k}={v}"
                                                 for k, v in ends.items()))
            u.join((ba, ja, str(pin)), (bb, jb, str(pin)))

    joined = defaultdict(set)
    for node in list(u.parent):
        _board, r, p = node
        if r.startswith("#") or r in LINK_REFS:
            continue
        joined[u.find(node)].add((r, p))
    got = {frozenset(g) for g in joined.values() if g}
    want = set()
    for nodes in ref.values():
        g = frozenset((r, p) for r, p in nodes if not r.startswith("#"))
        if g:
            want.add(g)

    for group in sorted(want - got, key=describe):
        near = max(got, key=lambda g: len(g & group), default=frozenset())
        fail.append("net missing from the boards: " + describe(group)
                    + ("\n        nearest joined net: " + describe(near)
                       if near & group else ""))
    for group in sorted(got - want, key=describe):
        fail.append("net the reference does not have: " + describe(group))

    nodes = sum(len(g) for g in want)
    print(f"\n{len(want)} nets / {nodes} nodes to account for; the four boards "
          f"welded at their ribbons give {len(got)} nets")
    if fail:
        print(f"\nFAIL  {len(fail)} problem(s):")
        for f in fail:
            print("   -", f)
        return 1
    print("\nPASS  common + digital + channel L + channel R, welded at the "
          "ribbons, is exactly the reference sheet")
    for ba, ja, bb, jb, pins in LINKS:
        crossing = sorted({net for _p, net, _k in pins})
        print(f"      {ja}-{jb}: " + ", ".join(crossing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
