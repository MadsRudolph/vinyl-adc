#!/usr/bin/env python3
"""Gate: the boards, plugged into their stacking bus, ARE the reference sheet.

    py -3.13 tools/check_split.py

`vinyl_adc.kicad_sch` is the whole converter on one page.  It is the sheet the
testbenches link back to and the one `check_intent.py` reads, and it is never
milled.  What gets cut is four boards from THREE artworks:

    vinyl_adc_power       power and the +/-2.5 V reference
    vinyl_adc_digital     the clock, the interleave mux, the level shift, the Pi
    vinyl_adc_channel_l   one modulator channel  ) THE SAME ARTWORK,
    vinyl_adc_channel_r   the other              ) milled twice

Nothing else enforces that those still add up to it.  They all come out of one
layout script and share block functions, but sharing a *drawing* is not sharing
*connectivity*: a block called from the wrong composer, a label misspelt at one
end of the bus, a net that quietly ends up crossing without a pin to cross on
-- every one of those leaves score, ERC, geometry and footprint checks
perfectly green on all five files, because each file is individually
consistent.  The fault only exists in the relationship between them.

So this welds the bus, models the one shunt that is deliberately NOT in any
netlist, drops the connectors, and requires the resulting partition of every
(ref, pin) node to be IDENTICAL to the reference sheet's.  A part that moved to
another board is invisible here, and should be -- that is the whole point of
splitting.  A part that was lost, doubled, or left connected to something it
should not be, is not.

It also proves the two channel boards are ONE artwork: channel R's netlist must
be channel L's with every refdes number raised by forty.  If that ever stops
being true, the second board is a second design and nobody has noticed.

TWO THINGS THIS SHAPE HAS THAT THE OLD FOUR-BOARD SPLIT DID NOT
---------------------------------------------------------------
1.  The bus is SHARED, not point-to-point.  The old split cabled a `common`
    board to each of the other three with its own ribbon, so welding meant
    joining pairs.  There is no `common` board any more; every board carries
    the SAME 2x8 at the SAME coordinates and they stack on 11 mm standoffs.
    Pin n of every connector is one node, so the weld is an n-way join.

2.  The Q-select shunt carries connectivity that NO netlist contains.  Both
    channel boards are the same copper, so nothing etched can say which
    channel a board is; the shunt on J21/J61 does.  1-2 makes it left, 2-3
    right, and the netlist is identical either way -- deliberately, since that
    is what lets one artwork be milled twice.  The reference sheet has the
    channels already committed (`QL` reaches U23.5, `QR` reaches U63.5), so
    reproducing it means fitting the shunts here the way they are fitted on
    the bench.  Without this the check reports two spurious net splits and
    two spurious extra nets, and every one of them is a lie.
"""

import os
import re
import sys
from collections import defaultdict
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from check_intent import load, netof                          # noqa: E402
from vinyl_adc_layout import LINK_BUS                          # noqa: E402

REF = "vinyl_adc"
POWER, DIGITAL = "vinyl_adc_power", "vinyl_adc_digital"
CH_L, CH_R = "vinyl_adc_channel_l", "vinyl_adc_channel_r"
BOARDS = (POWER, DIGITAL, CH_L, CH_R)

# Which 2x8 is the stacking bus on each board.  paths.py owns this because the
# export scripts need it too; re-deriving it here would let the two drift.
BUS = paths.BUS_REF

# Refdes that exist only because the design was split, so the reference sheet
# has no such part.  They are dropped before the partitions are compared, and
# they keep their own number when channel L is remapped onto channel R -- both
# channel boards call the bus J7 because they are one artwork.
BUS_REFS = set(BUS.values())

# The Q-select shunt, and which way it is fitted on each channel board.
# `q_select()` in vinyl_adc_layout.py: pin 1 = QL, pin 2 = Q_OUT, pin 3 = QR.
Q_SEL = {CH_L: ("J21", ("1", "2")),      # shunt 1-2 -> this board drives QL
         CH_R: ("J61", ("2", "3"))}      # shunt 2-3 -> this board drives QR
Q_SEL_REFS = {ref for ref, _ in Q_SEL.values()}

# Everything dropped from the node comparison: bus connectors and the shunt
# headers.  Both are real parts that get soldered; neither is on the one-page
# sheet, which draws the converter as though the split had never happened.
DROP_REFS = BUS_REFS | Q_SEL_REFS

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
    """R20 -> R60, C24 -> C64, J21 -> J61; the shared bus keeps its number."""
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", ref)
    if not m or ref in BUS_REFS:
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


def check_bus_pinout(nets, fail):
    """Every board's bus connector must agree, pin for pin, on one pinout.

    This is the check that catches a label misspelt at one end.  Welding pin n
    to pin n happens whatever the nets are called, so without this a board
    whose J7.8 says `MCLK_` instead of `MCLK` still welds into one node and
    still reproduces the reference -- and then mills a connector that means
    something different from the one above it in the stack.
    """
    ok = True
    for pin, net, _kind in LINK_BUS:
        got = {}
        for board in BOARDS:
            got[board] = netof(nets[board], BUS[board], str(pin))
        missing = [b for b, v in got.items() if v is None]
        if missing:
            ok = False
            fail.append(f"bus pin {pin} ({net}) is on no net at all on "
                        + ", ".join(sorted(missing)))
        elif len(set(got.values())) != 1 or next(iter(got.values())) != net:
            ok = False
            fail.append(
                f"bus pin {pin} should be {net} on every board, "
                + ", ".join(f"{b.replace('vinyl_adc_', '')}={v}"
                            for b, v in sorted(got.items())))
    if ok:
        print(f"  the stacking bus agrees on all {len(BOARDS)} boards "
              f"({len(LINK_BUS)} pins: "
              + ", ".join(sorted({n for _p, n, _k in LINK_BUS})) + ")")


def main():
    fail = []
    ref = netlist(REF)
    nets = {name: netlist(name) for name in BOARDS}
    print(f"reference {REF}: {len(ref)} nets")
    for name in BOARDS:
        print(f"  {name}: {len(nets[name])} nets  (bus {BUS[name]})")
    print()
    check_one_artwork(nets[CH_L], nets[CH_R], fail)
    check_bus_pinout(nets, fail)

    # -- no refdes may exist on two boards, connectors excepted --------------
    # If one did, a part would be built twice and counted once, and the
    # comparison below would be meaningless rather than wrong. The channel
    # boards share J7 by design: they are the same artwork.
    seen = defaultdict(set)
    for name in BOARDS:
        for nodes in nets[name].values():
            for r, _ in nodes:
                if not r.startswith("#") and r not in BUS_REFS:
                    seen[r].add(name)
    for r, where in sorted(seen.items()):
        if len(where) > 1:
            fail.append(f"{r} is on {' and '.join(sorted(where))}")

    # -- weld the stack ------------------------------------------------------
    u = Union()
    for name in BOARDS:
        for nodes in nets[name].values():
            nodes = sorted((name,) + n for n in nodes)
            for n in nodes:
                u.find(n)           # register even a one-node net: an NC pin
                u.join(nodes[0], n)  # is still a net the reference has
    # The bus is shared, so pin n of every board's connector is ONE node.
    for pin, _net, _kind in LINK_BUS:
        ends = [(b, BUS[b], str(pin)) for b in BOARDS]
        for other in ends[1:]:
            u.join(ends[0], other)
    # The shunt that decides which channel a board is. Not in any netlist --
    # see the module docstring.
    for board, (ref_j, (a, b)) in Q_SEL.items():
        for pin in (a, b):
            if netof(nets[board], ref_j, pin) is None:
                fail.append(f"{ref_j}.{pin} is on no net on "
                            f"{board} -- the Q-select shunt cannot be modelled")
        u.join((board, ref_j, a), (board, ref_j, b))

    joined = defaultdict(set)
    for node in list(u.parent):
        _board, r, p = node
        if r.startswith("#") or r in DROP_REFS:
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
    print(f"\n{len(want)} nets / {nodes} nodes to account for; the "
          f"{len(BOARDS)} boards welded at the stacking bus give "
          f"{len(got)} nets")
    if fail:
        print(f"\nFAIL  {len(fail)} problem(s):")
        for f in fail:
            print("   -", f)
        return 1
    print("\nPASS  power + digital + channel L + channel R, stacked on the "
          "2x8 bus, is exactly the reference sheet")
    print("      bus carries: "
          + ", ".join(sorted({n for _p, n, _k in LINK_BUS})))
    for board, (ref_j, (a, b)) in sorted(Q_SEL.items()):
        side = "LEFT" if a == "1" else "RIGHT"
        print(f"      {board.replace('vinyl_adc_', '')}: shunt {ref_j} "
              f"{a}-{b} = {side}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
