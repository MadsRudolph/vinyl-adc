#!/usr/bin/env python3
"""Gate 3: does the drawn netlist match the circuit I meant to draw?

sch_score and ERC both pass happily on a schematic that is beautifully drawn
and electrically wrong.  On a redraw you can diff against the old board; on a
new design there is nothing to diff against, so the intent has to be written
down separately -- which is what this file is.

Reads the netlist KiCad itself exports, so it checks the shipped artefact
rather than the drawing script's own idea of connectivity.

    py -3.13 check_intent.py ../vinyl_adc.net
"""

import collections
import os
import subprocess
import sys

sys.path.insert(0, r"C:\Users\Mads2\.claude\skills\kicad-schematic\scripts")
import sexpdata  # noqa: E402

KICAD = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"


def load(netpath, schpath):
    if (not os.path.exists(netpath) or
            os.path.getmtime(netpath) < os.path.getmtime(schpath)):
        subprocess.run([KICAD, "sch", "export", "netlist", "--format",
                        "kicadsexpr", "-o", netpath, schpath], check=True,
                       capture_output=True)
    d = sexpdata.loads(open(netpath, encoding="utf-8").read())

    def kids(node, name):
        return [c for c in node if isinstance(c, list) and str(c[0]) == name]

    def val(node, name):
        k = kids(node, name)
        return str(k[0][1]) if k and len(k[0]) > 1 else None

    nets = {}
    for blk in kids(d, "nets"):
        for n in kids(blk, "net"):
            nets[val(n, "name")] = {(val(x, "ref"), val(x, "pin"))
                                    for x in kids(n, "node")}
    return nets


def netof(nets, ref, pin):
    for name, nodes in nets.items():
        if (ref, pin) in nodes:
            return name
    return None


FAILURES = []


def same(nets, label, *pins):
    """Every (ref, pin) must land on one net."""
    got = {p: netof(nets, *p) for p in pins}
    names = set(got.values())
    if len(names) != 1 or None in names:
        FAILURES.append(f"{label}: expected one net, got " +
                        ", ".join(f"{r}.{p}->{n}" for (r, p), n in got.items()))
        return None
    return names.pop()


def distinct(nets, label, *pins):
    got = [(p, netof(nets, *p)) for p in pins]
    names = [n for _, n in got]
    if len(set(names)) != len(names):
        FAILURES.append(f"{label}: these should be separate nets but are not: "
                        + ", ".join(f"{r}.{p}->{n}" for (r, p), n in got))


def exactly(nets, label, net_name, expected):
    nodes = nets.get(net_name)
    if nodes is None:
        FAILURES.append(f"{label}: no net named {net_name!r}")
        return
    exp = set(expected)
    if nodes != exp:
        FAILURES.append(
            f"{label}: net {net_name!r} membership wrong\n"
            f"      missing: {sorted(exp - nodes)}\n"
            f"      extra:   {sorted(nodes - exp)}")


def channel(nets, ch, U, C, R, DN, DP):
    """One modulator channel.  U=TL074 ref, C=LM311 ref, R=lambda role->refdes."""
    p = f"[{ch}]"
    # --- the three integrators: each summing node carries exactly its own
    #     input, its DAC leg, its offset leg and its feedback cap
    same(nets, f"{p} int1 summing node",
         (R("Rin"), "2"), (R("Rd1"), "2"), (R("Ro1"), "2"),
         (R("C1"), "1"), (U, "2"))
    same(nets, f"{p} int1 output -> int2 input",
         (U, "1"), (R("C1"), "2"), (R("R2"), "1"))
    same(nets, f"{p} int2 summing node",
         (R("R2"), "2"), (R("Rd2"), "2"), (R("Ro2"), "2"), (R("Rg"), "2"),
         (R("C2"), "1"), (U, "6"))
    same(nets, f"{p} int2 output -> int3 input",
         (U, "7"), (R("C2"), "2"), (R("R3"), "1"))
    same(nets, f"{p} int3 summing node",
         (R("R3"), "2"), (R("Rd3"), "2"), (R("Ro3"), "2"),
         (R("C3"), "1"), (U, "9"))
    # int3 output fans out three ways: its own cap, the resonator inverter and
    # the quantiser.  If the comparator tap went missing the loop still looks
    # complete and simply never quantises.
    same(nets, f"{p} int3 output -> inverter + comparator",
         (U, "8"), (R("C3"), "2"), (R("Ri"), "1"), (R("Rs"), "1"))
    # --- resonator: inverter output must reach int2 through Rg, and the
    #     inverter must actually invert (Rf across it), or g has the wrong sign
    same(nets, f"{p} inverter summing node",
         (R("Ri"), "2"), (R("Rf"), "1"), (U, "13"))
    same(nets, f"{p} inverter output -> resonator resistor",
         (U, "14"), (R("Rf"), "2"), (R("Rg"), "1"))
    # --- quantiser
    same(nets, f"{p} comparator summing node",
         (R("Rs"), "2"), (R("Rk0"), "2"), (R("Rsh"), "2"), (R("Rb"), "2"),
         (C, "3"))
    same(nets, f"{p} comparator output", (C, "7"), (R("Rpu"), "2"))
    # --- DAC polarity.  int1 and int3 take the INVERTED gate, int2 and the
    #     ELD path take the non-inverted one.  Swapping any of these turns
    #     negative feedback into positive and the loop latches.
    n1 = netof(nets, R("Rd1"), "1")
    n3 = netof(nets, R("Rd3"), "1")
    n2 = netof(nets, R("Rd2"), "1")
    nk = netof(nets, R("Rk0"), "1")
    if not (n1 == n3 == DN):
        FAILURES.append(f"{p} int1/int3 DAC legs should both be {DN}, "
                        f"got {n1} and {n3}")
    if not (n2 == nk == DP):
        FAILURES.append(f"{p} int2/ELD DAC legs should both be {DP}, "
                        f"got {n2} and {nk}")
    distinct(nets, f"{p} the two DAC polarities must not be shorted",
             (R("Rd1"), "1"), (R("Rd2"), "1"))
    # --- the three offset legs all return to the -2.5 V reference
    for role in ("Ro1", "Ro2", "Ro3"):
        if netof(nets, R(role), "1") != "VREF_N":
            FAILURES.append(f"{p} {R(role)}.1 should sit on VREF_N, got "
                            f"{netof(nets, R(role), '1')}")
    if netof(nets, R("Rb"), "1") != "+5V":
        FAILURES.append(f"{p} {R('Rb')}.1 (threshold-centring leg) should sit "
                        f"on +5V, got {netof(nets, R('Rb'), '1')}")
    if netof(nets, R("Rsh"), "1") != "VREF_P":
        FAILURES.append(f"{p} {R('Rsh')}.1 should sit on VREF_P")
    if netof(nets, C, "2") != "VREF_P":
        FAILURES.append(f"{p} comparator + input should sit on VREF_P, got "
                        f"{netof(nets, C, '2')}")
    # LM311 runs single-supply here so it stays off the charge pump
    if netof(nets, C, "8") != "+5V":
        FAILURES.append(f"{p} LM311 V+ should be +5V")
    if netof(nets, C, "4") != "GND":
        FAILURES.append(f"{p} LM311 V- should be GND (single supply)")
    # TL074 package must straddle both rails
    if netof(nets, U, "4") != "+5V" or netof(nets, U, "11") != "-5V":
        FAILURES.append(f"{p} TL074 supply pins wrong: "
                        f"4->{netof(nets, U, '4')} 11->{netof(nets, U, '11')}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sch = os.path.join(here, "..", "vinyl_adc.kicad_sch")
    net = os.path.join(here, "..", "vinyl_adc.net")
    nets = load(net, sch)
    print(f"{len(nets)} nets in {os.path.basename(sch)}")

    L = {"Rin": "R21", "Rd1": "R22", "Ro1": "R23", "R2": "R24", "Rd2": "R25",
         "Ro2": "R26", "Rg": "R27", "R3": "R28", "Rd3": "R29", "Ro3": "R30",
         "Ri": "R31", "Rf": "R32", "Rs": "R33", "Rk0": "R34", "Rsh": "R35",
         "Rb": "R36", "Rpu": "R37", "C1": "C22", "C2": "C23", "C3": "C24"}
    Rr = {k: ("R%d" % (int(v[1:]) + 40)) if v[0] == "R" else
          ("C%d" % (int(v[1:]) + 40)) for k, v in L.items()}

    channel(nets, "L", "U20", "U21", L.get, "DACN_L", "DACP_L")
    channel(nets, "R", "U60", "U61", Rr.get, "DACN_R", "DACP_R")

    # ---- clock tree and the Pi interface -------------------------------
    exactly(nets, "clock divider input", "CLK6M", {("U3", "3"), ("U4", "10")})
    same(nets, "MCLK clocks both quantisers and selects the mux",
         ("U4", "7"), ("U5", "3"), ("U5", "11"), ("U6", "1"))
    same(nets, "BCLK reaches the level shifter", ("U4", "9"), ("U8", "3"))
    same(nets, "LRCLK reaches the level shifter", ("U4", "4"), ("U8", "7"))
    same(nets, "mux output is the Pi's data line", ("U6", "4"), ("U8", "11"))
    same(nets, "L quantiser Q -> mux and DAC", ("U5", "5"), ("U6", "3"),
         ("U7", "1"))
    same(nets, "R quantiser Q -> mux and DAC", ("U5", "9"), ("U6", "2"),
         ("U7", "5"))
    same(nets, "L comparator -> L flip-flop D", ("U21", "7"), ("U5", "2"))
    same(nets, "R comparator -> R flip-flop D", ("U61", "7"), ("U5", "12"))
    distinct(nets, "the four clock-tree nets must be separate",
             ("U4", "9"), ("U4", "7"), ("U4", "3"), ("U4", "4"))
    # the jumper must NOT short the can to GPCLK0 -- a vertical run down its
    # pin column would, and did
    distinct(nets, "clock jumper does not short its three pins",
             ("J1", "1"), ("J1", "2"), ("J1", "3"))
    same(nets, "oscillator drives jumper pin 1", ("X1", "5"), ("J1", "1"))
    # charge pump: every 74HC244 buffer really is in parallel
    same(nets, "pump drive input", ("U4", "3"),
         *[("U1", n) for n in ("2", "4", "6", "8", "17", "15", "13", "11")])
    same(nets, "pump drive output",
         *[("U1", n) for n in ("18", "16", "14", "12", "3", "5", "7", "9")],
         ("C4", "1"))
    # supplies must be three separate nets
    distinct(nets, "supply rails separate", ("J2", "1"), ("J2", "3"), ("J2", "2"))
    if netof(nets, "J2", "1") != "+5V":
        FAILURES.append("J2.1 should be +5V")
    if netof(nets, "J2", "3") != "+3V3":
        FAILURES.append("J2.3 should be +3V3")

    # nothing may short a rail pair anywhere
    for a, b in (("+5V", "GND"), ("-5V", "GND"), ("+5V", "-5V"),
                 ("+3V3", "+5V"), ("VREF_P", "VREF_N")):
        if a in nets and b in nets and nets[a] & nets[b]:
            FAILURES.append(f"{a} and {b} share nodes: {nets[a] & nets[b]}")

    # no passive with both ends on one net
    for name, nodes in nets.items():
        byref = collections.defaultdict(set)
        for r, pin in nodes:
            byref[r].add(pin)
        for r, pins in byref.items():
            if r[0] in "RCD" and len(pins) > 1:
                FAILURES.append(f"net {name!r} shorts both ends of {r}")

    print()
    if FAILURES:
        print(f"FAIL  {len(FAILURES)} intent mismatch(es):")
        for f in FAILURES:
            print("   -", f)
        return 1
    print("PASS  drawn netlist matches the intended circuit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
