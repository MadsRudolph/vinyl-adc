#!/usr/bin/env python3
r"""Place, route and check one HAT board, retrying FreeRouting costs until
DRC reports nothing unconnected.

    python3 tools/hat_route.py rev_d <netlist.json> [--scratch DIR]
    python3 tools/hat_route.py rev_e <netlist.json> [--scratch DIR]

Each attempt rebuilds the placed board from scratch (hat_board.py; the
placement is seeded, so it is the same every time), routes it
(route_4layer.py), and on the SMD board then gives every SMD plane pad its
via where the routing left room, and drops a via onto whatever plane
island DRC still reports (fanout.py, then fanout.py --islands).
That order is forced: FreeRouting 2.4.1 connects most SMD plane pads
itself but throws a NullPointerException -- and never returns -- on a
board that already carries copper, so the fan-out cannot go in first.

FreeRouting is deterministic for identical input, so a run that leaves a
net open is retried with different costs, not the same.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
K = os.path.dirname(HERE)
KICAD = "/usr/bin/kicad-cli"
COSTS = ((1.9, 25), (1.5, 15), (2.5, 40), (1.2, 10), (3.0, 60), (2.0, 30),
         (1.0, 8), (4.0, 80))
QUIET = ("m_choices", "Debug:", "memory leak")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = "\n".join(line for line in (r.stdout + r.stderr).splitlines()
                    if not any(q in line for q in QUIET))
    return r.returncode, out


def drc(pcb):
    rep = os.path.splitext(pcb)[0] + ".drc.json"
    run([KICAD, "pcb", "drc", "--format", "json", "--severity-all",
         "--schematic-parity", "-o", rep, pcb])
    d = json.load(open(rep, encoding="utf-8"))
    errs = [v for v in d["violations"] if v["severity"] == "error"]
    warns = [v for v in d["violations"] if v["severity"] == "warning"]
    return d, errs, warns, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rev")
    ap.add_argument("json")
    ap.add_argument("--scratch", default="/tmp/hat_route")
    ap.add_argument("--passes", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    os.makedirs(a.scratch, exist_ok=True)
    pcb = os.path.join(K, a.rev, f"vinyl_adc_{a.rev}.kicad_pcb")
    smd = a.rev == "rev_e"
    for against, via in COSTS:
        print(f"== costs {against} / {via}", flush=True)
        rc, out = run([sys.executable, os.path.join(HERE, "hat_board.py"),
                       a.rev, a.json, pcb, "--seed", str(a.seed)])
        print("\n".join(line for line in out.splitlines()
                        if any(k in line for k in ("wire", "WARNING", "wrote",
                                                   "decoupling"))), flush=True)
        if rc:
            print(out)
            return 1
        rc, out = run([sys.executable, os.path.join(HERE, "route_4layer.py"),
                       pcb, "--passes", str(a.passes), "--out", a.scratch,
                       "--planes", "GND,+5V,+5VA", "--against-cost",
                       str(against), "--via-cost", str(via)])
        print("\n".join(out.strip().splitlines()[-3:]), flush=True)
        if smd:
            # every SMD plane pad its via where the routing left room, then
            # a second pass for the islands DRC still reports
            rc, out = run([sys.executable, os.path.join(HERE, "fanout.py"),
                           pcb])
            print(out.strip().splitlines()[-1], flush=True)
            _d, _e, _w, rep = drc(pcb)
            rc, out = run([sys.executable, os.path.join(HERE, "fanout.py"),
                           pcb, "--islands", rep])
            print(out.strip().splitlines()[-1], flush=True)
        d, errs, warns, rep = drc(pcb)
        unc = len(d["unconnected_items"])
        print(f"  DRC: {unc} unconnected, {len(errs)} errors, "
              f"{len(warns)} warnings, "
              f"{len(d.get('schematic_parity', []))} parity items", flush=True)
        if unc == 0 and not errs:
            print(f"clean with costs {against} / {via}")
            return 0
    print("no clean route")
    return 1


if __name__ == "__main__":
    sys.exit(main())
