#!/usr/bin/env python3
"""Gate: the rev C board IS the reference sheet, plus exactly three changes.

    python3 tools/check_rev_c.py

`vinyl_adc_rev_c.kicad_sch` is drawn by the same block functions as the
one-page reference, but sharing a drawing is not sharing connectivity (see
check_split.py for why).  This welds the parts that rev C adds IN SERIES with
a reference net -- the 5 V inlet bead FB1 and the two 470 R in BCLK/LRCLK --
drops both sheets' Pi connector (an 8-way pigtail on the reference, the Pi's
own 40-pin socket here), and requires the partition of every remaining
(ref, pin) node to be IDENTICAL.  U2 changing from TL072 to LM358 is
pin-compatible and invisible here, as it should be.
"""
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                  # noqa: E402
from check_intent import load                                 # noqa: E402
from check_split import Union, describe                       # noqa: E402

REF, REVC = "vinyl_adc", "vinyl_adc_rev_c"
SERIES = ("FB1", "R12", "R13")     # two-pin parts welded through
DROP = {"J2"} | set(SERIES)        # gone from the comparison on both sides


def groups(nets, weld=(), drop=()):
    u = Union()
    for nodes in nets.values():
        nodes = sorted(nodes)
        for n in nodes:
            u.find(n)
            u.join(nodes[0], n)
    for ref in weld:
        pins = sorted(p for r, p in u.parent if r == ref)
        if len(pins) != 2:
            raise SystemExit(f"{ref}: expected 2 pins to weld, found {pins}")
        u.join((ref, pins[0]), (ref, pins[1]))
    out = defaultdict(set)
    for node in list(u.parent):
        r, _p = node
        if r.startswith("#") or r in drop:
            continue
        out[u.find(node)].add(node)
    return {frozenset(g) for g in out.values() if g}


def main():
    ref = load(paths.net(REF), paths.sch(REF))
    revc = load(paths.net(REVC), paths.sch(REVC))
    want = groups(ref, drop=DROP)
    got = groups(revc, weld=SERIES, drop=DROP)
    fail = []
    for g in sorted(want - got, key=describe):
        near = max(got, key=lambda h: len(h & g), default=frozenset())
        fail.append("net missing from rev C: " + describe(g)
                    + ("\n        nearest: " + describe(near) if near & g else ""))
    for g in sorted(got - want, key=describe):
        fail.append("net the reference does not have: " + describe(g))
    # the three additions must actually be in series with the nets they claim
    for ref_, net in (("FB1", "+5V"), ("R12", "PI_BCLK"), ("R13", "PI_LRCLK")):
        on = {n for n, nodes in revc.items() if any(r == ref_ for r, _ in nodes)}
        if net not in on:
            fail.append(f"{ref_} is on {sorted(on)}, not {net}")
    u2 = {v for v in re.findall(r'\(ref "U2"\)\s*\(value "([^"]+)"\)',
                                open(paths.net(REVC), encoding="utf-8").read())}
    if u2 != {"LM358"}:
        fail.append(f"U2 is {u2}, rev C wants the LM358 (design-notes 10b')")
    print(f"reference {len(want)} nets, rev C {len(got)} nets after welding "
          f"{', '.join(SERIES)} and dropping {', '.join(sorted(DROP))}")
    if fail:
        print(f"FAIL  {len(fail)} problem(s):")
        for f in fail:
            print("   -", f)
        return 1
    print("OK    rev C is the reference sheet plus FB1, R12, R13 and the LM358")
    return 0


if __name__ == "__main__":
    sys.exit(main())
