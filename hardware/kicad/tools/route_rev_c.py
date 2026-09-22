#!/usr/bin/env python3
r"""Route the rev C board on four layers with FreeRouting, headlessly enough.

    PYTHONPATH=<pcbnew shim> python3 tools/route_rev_c.py rev_c/vinyl_adc_rev_c.kicad_pcb \
        [--passes 40] [--out DIR]

F.Cu and B.Cu carry signals; In1.Cu (GND) and In2.Cu (+5V) are solid planes
and are marked `(type power)` in the DSN so the router never lays a trace on
them but still counts their nets as connected.  Through-hole pads reach the
planes on their own, so GND and +5V need no tracks at all.

FreeRouting 1.9.0 has no headless mode (2.x needs Java 25, which this box
does not have), so before it starts, a session-only Hyprland window rule
sends anything with "freerouting" in its class to a silent special
workspace.  The user has been explicit that a window stealing focus mid-run
is not acceptable; the rule is the mitigation, and `hyprctl clients` is read
afterwards to confirm the window actually landed there.  On a machine
without Hyprland the rule step is skipped and the window will show.

The board must be UNROUTED when it arrives here: `board.Remove()` on a track
poisons the SWIG runtime for the rest of the process (every later object
comes back as a bare SwigPyObject -- the same trap pcb_pours.py documents for
zones), so this script refuses a routed board rather than stripping it.
Rebuild the placement with rev_c_board.py and route again.  FreeRouting is
deterministic for identical input, so a run that leaves a net open is
retried with different via/direction costs, not with the same ones.

The SES import replaces the board's tracks; zones survive it and are refilled.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

import pcbnew

JAR = os.path.expanduser("~/.freerouting/freerouting-1.9.0.jar")
KICAD = next(p for p in ("/usr/bin/kicad-cli",
                         r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
             if os.path.exists(p))
POWER_LAYERS = ("In1.Cu", "In2.Cu")


def mask_power(dsn, layer):
    txt = open(dsn, encoding="utf-8").read()
    pat = re.compile(r"\(layer " + re.escape(layer) + r"\s*\r?\n(\s*)\(type signal\)")
    out, n = pat.subn(lambda m: f"(layer {layer}\n{m.group(1)}(type power)", txt)
    if not n:
        raise SystemExit(f"no (layer {layer} ... (type signal)) in the DSN")
    open(dsn, "w", encoding="utf-8", newline="").write(out)


def set_rules(dsn, against_cost, via_cost):
    txt = open(dsn, encoding="utf-8").read()
    rule = (f"\n  (rule\n"
            f"    (against_preferred_direction_trace_costs {against_cost})\n"
            f"    (via_costs {via_cost})\n"
            f"  )\n")
    i = txt.rfind("(structure")
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


def hide_window():
    if not shutil.which("hyprctl"):
        return False
    r = subprocess.run(
        ["hyprctl", "eval",
         'hl.window_rule({name="freerouting-hidden", '
         'match={class="^(.*[Ff]reerouting.*|.*[Jj]ava.*)$"}, '
         'workspace="special:freerouting silent"})'],
        capture_output=True, text=True)
    return r.stdout.strip() == "ok"


def where_is_window():
    try:
        cl = json.loads(subprocess.run(["hyprctl", "clients", "-j"],
                                       capture_output=True, text=True).stdout)
    except Exception:
        return []
    return [(c.get("class"), c.get("workspace", {}).get("name"))
            for c in cl if re.search(r"(?i)freerouting|java", c.get("class") or "")]


def freeroute(dsn, ses, passes, timeout):
    t0 = time.time()
    # cwd = the output dir: FreeRouting drops a logs/ directory wherever it runs
    p = subprocess.Popen(["java", "-jar", JAR, "-de", dsn, "-do", ses,
                          "-mp", str(passes)], cwd=os.path.dirname(dsn),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    seen = []
    timed_out = False
    try:
        for _ in range(30):
            time.sleep(1)
            seen = where_is_window()
            if seen or p.poll() is not None:
                break
        out, _ = p.communicate(timeout=max(1, timeout - (time.time() - t0)))
    except subprocess.TimeoutExpired:
        timed_out = True
        p.kill()
        p.communicate()
    dt = time.time() - t0
    size = os.path.getsize(ses) if os.path.exists(ses) else 0
    print(f"  freerouting {dt:.0f}s, window {seen or 'not seen'}, ses {size} bytes"
          + (" (killed on timeout; SES on disk decides)" if timed_out else ""))
    if size == 0:
        raise SystemExit("FreeRouting wrote no SES")


def drc(pcb):
    rep = os.path.splitext(pcb)[0] + ".drc.json"
    subprocess.run([KICAD, "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", rep, pcb], capture_output=True, text=True)
    d = json.load(open(rep, encoding="utf-8"))
    kinds = {}
    for v in d.get("violations", []):
        k = (v["severity"], v["type"])
        kinds[k] = kinds.get(k, 0) + 1
    unc = d.get("unconnected_items", [])
    return kinds, unc, rep


def summary(pcb):
    b = pcbnew.LoadBoard(pcb)
    per, vias = {}, 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias += 1
        else:
            name = b.GetLayerName(t.GetLayer())
            per[name] = per.get(name, 0) + pcbnew.ToMM(t.GetLength())
    return per, vias


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcb")
    ap.add_argument("--passes", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", default=None)
    ap.add_argument("--via-cost", type=float, default=25)
    ap.add_argument("--against-cost", type=float, default=1.9)
    a = ap.parse_args()
    out = a.out or os.path.dirname(os.path.abspath(a.pcb))
    stem = os.path.splitext(os.path.basename(a.pcb))[0]
    dsn = os.path.join(out, stem + ".dsn")
    ses = os.path.join(out, stem + ".ses")

    b = pcbnew.LoadBoard(a.pcb)
    if len(list(b.GetTracks())):
        raise SystemExit("board already has tracks: rebuild it with "
                         "rev_c_board.py before routing (see docstring)")
    if not pcbnew.ExportSpecctraDSN(b, dsn):
        raise SystemExit("DSN export failed")
    txt = open(dsn, encoding="utf-8").read()
    planes = re.findall(r"\(plane\s+(\S+)", txt)
    print(f"  DSN: {len(re.findall(r'\(layer ', txt))} layers, planes {planes}")
    if "GND" not in planes or "+5V" not in planes:
        raise SystemExit("the inner-layer zones did not export as planes")
    for layer in POWER_LAYERS:
        mask_power(dsn, layer)
    set_rules(dsn, a.against_cost, a.via_cost)
    print(f"  costs: against {a.against_cost}, via {a.via_cost}, passes {a.passes}")

    print(f"  hyprland rule: {'set' if hide_window() else 'not available'}")
    freeroute(dsn, ses, a.passes, a.timeout)

    b = pcbnew.LoadBoard(a.pcb)
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise SystemExit("SES import failed")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(a.pcb, b)

    per, vias = summary(a.pcb)
    print("  copper: " + ", ".join(f"{k} {v:.0f} mm" for k, v in sorted(per.items()))
          + f", {vias} vias")
    kinds, unc, rep = drc(a.pcb)
    print(f"  DRC: {len(unc)} unconnected, "
          + (", ".join(f"{n} {k[1]}({k[0]})" for k, n in sorted(kinds.items())) or "clean"))
    print(f"  report {rep}")
    return 1 if unc else 0


if __name__ == "__main__":
    sys.exit(main())
