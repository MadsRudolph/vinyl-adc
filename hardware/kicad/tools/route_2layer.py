#!/usr/bin/env python3
"""Route ONE board on TWO copper layers, for the double-sided stock.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/route_2layer.py \
        <board.kicad_pcb> --out DIR [--mode signals-top|both-layers] [--passes N]

The rest of this project is single-sided: `place_route.py route` cuts the board
to one copper layer before it exports the DSN, on purpose, because a via has
nowhere to go on a board whose holes are drilled and never plated.  That is
still true of the power and digital artworks.  The CHANNEL artwork is cut from
double-sided stock, so it gets this instead.

WHAT CHANGES WHEN THERE ARE TWO LAYERS
--------------------------------------
Two of this project's hard-won rules INVERT here, and both are worth stating
because they read as regressions if you only know the single-sided story:

*   `against_preferred_direction_trace_costs` is a TWO-LAYER device -- one layer
    prefers horizontal, the other vertical, and the penalty is what makes a
    crossing worth a via.  On one layer it could only refuse to go vertical and
    it sliced the ground pour (gotchas 21).  Here it is doing the job it was
    designed for, so `both-layers` uses 1.9 and `signals-top` -- which is still
    a one-layer routing problem -- keeps 1.0.

*   `(plane <net> ...)` is a bet on one layer and a free win on two (gotchas
    22).  FreeRouting treats a plane's net as already connected and lays no
    copper for it.  With GND alone on B.Cu and the signals somewhere else, that
    is exactly right and the plane cannot be cut.

A VIA HERE IS A HAND-SOLDERED WIRE
----------------------------------
The holes are drilled, never plated, so every via is a short wire pushed
through and soldered both sides -- the same labour as the wire bridges this
project counts on the single-sided boards.  Count them the same way.  What is
NOT a via is a layer change AT A THROUGH-HOLE PAD: the component lead already
passes through the board, so a trace can leave that pad on either side for
free.  Every part on this board is through-hole, which is why two layers buys
so much here.

The other side of that coin is the one thing to check before committing: a pad
carrying copper on the TOP must be soldered on the top, and on a DIP the pad is
partly under the socket.  `--report-solder` counts those and says which are
under a body.  The `_LongPads` footprints this process mandates leave 1.8 mm of
pad outside the IC body (about 1.1 mm outside a socket), which is what makes it
possible at all.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

import pcbnew

JAR = os.path.expanduser(r"~\.freerouting\freerouting-1.9.0.jar")


STRIP = os.path.expanduser(
    r"~\.claude\skills\kicad-laser-pcb\scripts\strip_routing.py")


def strip_copper(pcb):
    """Remove every track and via -- TEXTUALLY, in a separate interpreter.

    Doing it in process with ``board.Remove()`` corrupts the pcbnew SWIG
    runtime: the very next ``LoadBoard`` returns a bare ``SwigPyObject`` with
    no methods on it, and the traceback points at the reload rather than at
    the removal that caused it. Measured here, not inherited folklore. The
    skill's own driver strips textually for the same reason.
    """
    subprocess.run(["py", "-3.13", STRIP, pcb], check=True, capture_output=True)
    b = pcbnew.LoadBoard(pcb)
    return len([t for t in b.GetTracks()])


def mask_layer_as_power(dsn, layer):
    """Make FreeRouting refuse to route signals on `layer`.

    A `(type power)` layer still conducts -- the plane on it is honoured -- but
    the router will not lay signal traces there. This is how `signals-top`
    keeps B.Cu as an uncut ground plane.
    """
    txt = open(dsn, encoding="utf-8").read()
    pat = re.compile(r"\(layer " + re.escape(layer) + r"\s*\r?\n(\s*)\(type signal\)")
    out, n = pat.subn(lambda m: f"(layer {layer}\n{m.group(1)}(type power)", txt)
    if not n:
        raise SystemExit(f"could not find a signal (layer {layer} ...) in the DSN")
    open(dsn, "w", encoding="utf-8", newline="").write(out)
    return n


def set_rules(dsn, against_cost, via_cost):
    """Inject autoroute costs before the closing paren of (network ...).

    Written into the DSN rather than passed on the command line because 1.9.0
    ignores most CLI tuning; the DSN is the only channel that reliably lands.
    """
    txt = open(dsn, encoding="utf-8").read()
    rule = (f"\n  (rule\n"
            f"    (against_preferred_direction_trace_costs {against_cost})\n"
            f"    (via_costs {via_cost})\n"
            f"  )\n")
    i = txt.rfind("(structure")
    if i < 0:
        raise SystemExit("no (structure ...) in the DSN")
    depth, j = 0, i
    while j < len(txt):
        if txt[j] == "(":
            depth += 1
        elif txt[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    txt = txt[:j] + rule + txt[j:]
    open(dsn, "w", encoding="utf-8", newline="").write(txt)


def freeroute(dsn, ses, passes, timeout=420):
    """Run FreeRouting, and do not let it hang the pipeline when it is done.

    1.9.0 headless writes the .ses and then does not always exit -- measured
    here as a java process sitting at 48 CPU-seconds over 115 minutes while a
    complete .ses lay on disk beside it. `subprocess.run(timeout=1800)` waits
    the whole half hour for a result that arrived in the first minute. So:
    a bounded wait, and on expiry the SES on disk decides. Kill the child
    either way -- an abandoned java is what wedges the NEXT run.

    Independently of that: a TRUNCATED .ses with exit code 0 and empty stderr
    is a real failure mode and its only tell is a suspiciously fast run, so
    both the runtime and the byte count are reported rather than an "ok".
    """
    t0 = time.time()
    p = subprocess.Popen(
        ["java", "-jar", JAR, "-de", dsn, "-do", ses, "-mp", str(passes)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out = False
    try:
        out, _err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out, out = True, ""
        p.kill()
        p.communicate()
    dt = time.time() - t0
    size = os.path.getsize(ses) if os.path.exists(ses) else 0
    print(f"    freerouting {dt:.1f}s  ses={size} bytes"
          + ("  (killed on timeout; SES on disk decides)" if timed_out else ""))
    if size == 0:
        print((out or "")[-1500:] or "(no stdout)")
        raise SystemExit("FreeRouting wrote no SES")
    return dt, size


def merge_tracks(src_pcb, dst_pcb):
    """Copy every track from `src_pcb` into `dst_pcb`, matching nets by NAME.

    Used to restore the copper that `ImportSpecctraSES` discarded. Net codes
    are per-board and need not agree between two files, so resolving by name
    is the only safe mapping; a code-to-code copy silently lands tracks on the
    wrong nets and the connectivity check then reports a board that is worse
    than either input.
    """
    src = pcbnew.LoadBoard(src_pcb)
    dst = pcbnew.LoadBoard(dst_pcb)
    by_name = {}
    for code, ni in dst.GetNetsByNetcode().items():
        by_name[ni.GetNetname()] = code
    added = 0
    for t in src.GetTracks():
        if t.GetClass() == "PCB_VIA":
            raise SystemExit("source board has vias; merge does not handle them")
        code = by_name.get(t.GetNetname())
        if code is None:
            raise SystemExit(f"net {t.GetNetname()!r} missing in the routed board")
        nt = pcbnew.PCB_TRACK(dst)
        nt.SetStart(t.GetStart())
        nt.SetEnd(t.GetEnd())
        nt.SetWidth(t.GetWidth())
        nt.SetLayer(t.GetLayer())
        nt.SetNetCode(code)
        dst.Add(nt)
        added += 1
    pcbnew.SaveBoard(dst_pcb, dst)
    return added


def refill(pcb):
    b = pcbnew.LoadBoard(pcb)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)


def report(pcb):
    b = pcbnew.LoadBoard(pcb)
    per = {}
    vias = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias += 1
            continue
        per[b.GetLayerName(t.GetLayer())] = per.get(
            b.GetLayerName(t.GetLayer()), 0) + 1
    return per, vias


def solder_report(pcb, tol_mm=0.30):
    """Pads that will actually need a joint on the TOP of the board.

    A pad needs one only if an F.Cu track ENDS ON IT -- not merely if its net
    has top copper somewhere else on the board. Getting that wrong inflates
    the count badly: on this artwork every net that touches the top at all
    would drag all of its pads in with it, and the whole point of the number
    is to decide whether the top-side soldering is tolerable.

    For each such pad, measure how far it reaches outside the footprint's
    F.Fab body outline. That overhang is the only place an iron can reach,
    because the component (or its socket) sits on the rest. The `_LongPads`
    DIP footprints this process mandates leave ~1.8 mm past the IC body and
    ~1.1 mm past a typical socket; an axial part or a header leaves the whole
    pad.
    """
    b = pcbnew.LoadBoard(pcb)
    tol = int(tol_mm * 1e6)
    ends = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" or t.GetLayer() != pcbnew.F_Cu:
            continue
        ends.append((t.GetStart(), t.GetNetCode()))
        ends.append((t.GetEnd(), t.GetNetCode()))
    rows = []
    for f in b.GetFootprints():
        fp = f.GetFPIDAsString()
        socket = "DIP-" in fp
        body = None
        for d in f.GraphicalItems():
            if d.GetLayer() == pcbnew.F_Fab:
                bb = d.GetBoundingBox()
                if body is None:
                    body = bb
                else:
                    body.Merge(bb)
        for p in f.Pads():
            pos = p.GetPosition()
            if not any(nc == p.GetNetCode()
                       and abs(e.x - pos.x) <= tol and abs(e.y - pos.y) <= tol
                       for e, nc in ends):
                continue
            pb = p.GetBoundingBox()
            over = None
            if body is not None:
                over = max(body.GetLeft() - pb.GetLeft(),
                           pb.GetRight() - body.GetRight(),
                           body.GetTop() - pb.GetTop(),
                           pb.GetBottom() - body.GetBottom()) / 1e6
            rows.append((f.GetReference(), p.GetNumber(), p.GetNetname(),
                         over, socket))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="signals-top",
                    choices=["signals-top", "both-layers", "leftovers-top"])
    ap.add_argument("--passes", type=int, default=20)
    ap.add_argument("--via-cost", type=int, default=200)
    ap.add_argument("--report-solder", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.board))[0]
    work = os.path.join(a.out, stem + ".kicad_pcb")
    src_dir = os.path.dirname(os.path.abspath(a.board))
    shutil.copy(a.board, work)
    for ext in (".kicad_pro", ".kicad_dru"):
        s = os.path.join(src_dir, stem + ext)
        if os.path.exists(s):
            shutil.copy(s, os.path.join(a.out, stem + ext))

    print(f"  {stem}  mode={a.mode}  passes={a.passes}")
    dsn = os.path.join(a.out, stem + ".dsn")
    ses = os.path.join(a.out, stem + ".ses")

    if a.mode == "leftovers-top":
        # Keep the bottom copper that already exists and give the router the
        # TOP layer for whatever the single-sided pass could not close.
        #
        # This is the cheapest possible use of double-sided stock, and the
        # arithmetic is why: a link left open on a single-sided board is a
        # wire, and a wire is soldered at BOTH ends -- exactly the two joints
        # a milled top-side trace between the same two pads would need. So
        # converting leftovers into top copper costs nothing in soldering and
        # removes the wire. Every other mode re-routes from scratch and moves
        # joints that were already fine.
        b = pcbnew.LoadBoard(work)
        n = 0
        for t in b.GetTracks():
            t.SetLocked(True)
            n += 1
        if not pcbnew.ExportSpecctraDSN(b, dsn):
            raise SystemExit("DSN export failed")
        print(f"    kept and locked {n} existing track(s) as (type fix)")
    else:
        left = strip_copper(work)
        print(f"    stripped copper, {left} track(s) left")
        b = pcbnew.LoadBoard(work)
        if not pcbnew.ExportSpecctraDSN(b, dsn):
            raise SystemExit("DSN export failed")

    if a.mode == "signals-top":
        # B.Cu becomes an uncut GND plane; every signal goes on F.Cu. Still a
        # ONE-layer routing problem, so keep costs isotropic (gotchas 21).
        mask_layer_as_power(dsn, "B.Cu")
        set_rules(dsn, "1.0", a.via_cost)
    else:
        # Genuine two-layer routing: anisotropy is now the right tool.
        set_rules(dsn, "1.9", a.via_cost)

    freeroute(dsn, ses, a.passes)
    b = pcbnew.LoadBoard(work)
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise SystemExit("SES import failed")
    pcbnew.SaveBoard(work, b)

    if a.mode == "leftovers-top":
        # ImportSpecctraSES REPLACES the routing; it does not merge. FreeRouting
        # honours `(type fix)` wires as obstacles but does not echo them back
        # into the .ses, so the import lands 62 new segments on a board that had
        # 259 -- and the check then reports 59 unconnected on what looked like a
        # successful run. Measured, not assumed: the DSN held 236 `(type fix)`
        # wires and the SES came back with none of them.
        #
        # So put the original copper back, matching nets BY NAME rather than by
        # net code: the two files are separate boards and nothing guarantees
        # their code numbering agrees.
        n = merge_tracks(a.board, work)
        print(f"    merged {n} original track(s) back in")
    refill(work)

    per, vias = report(work)
    print(f"    segments {per}   vias {vias}")
    if a.report_solder:
        rows = solder_report(work)
        sock = [r for r in rows if r[4]]
        tight = [r for r in rows if r[3] is not None and r[3] < 0.8]
        print(f"    pads needing a TOP joint: {len(rows)}"
              f"   of which on DIP sockets: {len(sock)}"
              f"   with <0.8 mm of pad clear of the body: {len(tight)}")
        for r in sorted(sock)[:24]:
            print(f"      socket {r[0]}.{r[1]} [{r[2]}] "
                  f"{r[3]:.2f} mm of pad outside the body")
    print(f"    -> {work}")


if __name__ == "__main__":
    main()
