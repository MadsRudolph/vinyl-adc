#!/usr/bin/env python3
r"""REV C: one 4-layer board from the rev C netlist, placed by hand, poured.

    python3 tools/pcb_netlist_json.py ...   (the skill's; makes rev_c.json)
    python3 tools/rev_c_board.py rev_c.json rev_c/vinyl_adc_rev_c.kicad_pcb

This is the fabricated successor to the four milled boards, and the two
things that shaped those layouts are gone here: tracks pass between DIP pins
(0.25 mm track, 0.2 mm clearance), and a via costs nothing.  What is left is
the circuit's own geography, which is the same as before:

    x 0..112                                 x 114..170
    y   4..56   CHANNEL L, left to right     DIGITAL clock, mux, level shift,
                                                     beside the Pi's 2x20 socket
    y  60..112  CHANNEL R, left to right     POWER  pump, +/-2.5 V reference
    inputs on the left edge; the Pi UNDER the right-hand 56 mm, its USB end
    overhanging the TOP edge so the tall connectors clear the board and its
    USB-C/HDMI edge flush with the right edge.

Stackup: F.Cu signals, In1.Cu solid GND, In2.Cu solid +5V, B.Cu signals.
Every part is through-hole on the top except the Pi socket, which is on the
copper side so the Pi plugs up into it HAT-style.  Placement reuses
pcb_floorplan's anchor/decouple/pack machinery; routing is FreeRouting via
route_rev_c.py.
"""
import json
import math
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcb_floorplan as FP                                    # noqa: E402

FPLIBS = [os.path.join(HERE, "..", "lib"), "/usr/share/kicad/footprints",
          r"C:\Program Files\KiCad\10.0\share\kicad\footprints"]

W, H = 170.0, 120.0            # outline, mm; origin top-left at (0, 0)

# PCBWay 4-layer standard capability is 0.1/0.1 mm and 0.2 mm drills; these
# leave a factor of two everywhere, which is what a first fabricated revision
# of a hand-built design wants.
RULES = dict(track=0.3, clearance=0.2, via=0.7, via_drill=0.35,
             supply_track=0.6, edge=0.4)
SUPPLY_NETS = ("-5V", "+3V3", "PUMP", "VREF_P", "VREF_N")

# -- the Raspberry Pi 4, seen from above the board ----------------------------
# Its 40-pin header is centred between its two near mounting holes (verified
# against KiCad's own Raspberry_Pi_Zero_Socketed footprint: header centre on
# the hole line, holes 29 mm either side, far holes 49 mm away on a Pi 4).
# The Pi's long axis runs up the board (y): SD end at y = 65, USB/Ethernet
# end at y = -20, overhanging the top edge.  Its header edge is the left side
# of the Pi zone and its USB-C/HDMI edge is flush with the right board edge.
# Handedness matters and was checked both ways: seen from above, pin 1 (3V3)
# is the INBOARD row at the SD end, pin 2 (5V) the row along the Pi's edge,
# and only this orientation lets a socket on the copper side land pins 1, 2
# and 39 on the Pi's pins.
PI_HDR = (117.5, 32.5)         # header centre; pins run along y
PI_HOLES = [(117.5, 3.5), (166.5, 3.5), (117.5, 61.5), (166.5, 61.5)]
PI_PIN1 = (PI_HDR[0] + 1.27, PI_HDR[1] + 24.13)
PI_PIN2 = (PI_HDR[0] - 1.27, PI_HDR[1] + 24.13)
PI_PIN39 = (PI_HDR[0] + 1.27, PI_HDR[1] - 24.13)

BOARD_HOLES = [(5, 5), (110, 5), (5, 115), (165, 115)]


def channel(n, by):
    """Anchors, decoupling pairs and pack rectangles for one channel band."""
    r = lambda k: f"R{n + k}"                                 # noqa: E731
    c = lambda k: f"C{n + k}"                                 # noqa: E731
    anchors = {
        f"J{n}":      (12, by + 10, 0),        # LINE IN, left edge
        f"RV{n}":     (12, by + 26, 0),        # level trim header, left edge
        f"U{n}":      (38, by + 14, 90),       # TL072  integrators 1, 2
        f"U{n + 2}":  (64, by + 14, 90),       # TL072  integrator 3, inverter
        f"U{n + 1}":  (90, by + 14, 90),       # LM311  quantiser
        f"U{n + 3}":  (92, by + 38, 90),       # 74HC74 retime
        f"U{n + 4}":  (64, by + 38, 90),       # 74HC04 DAC gates
    }
    decouple = {
        c(5): (f"U{n}", "above"), c(6): (f"U{n}", "below"),
        c(8): (f"U{n + 2}", "above"), c(9): (f"U{n + 2}", "below"),
        c(7): (f"U{n + 1}", "above"),
        c(10): (f"U{n + 3}", "below"), c(11): (f"U{n + 4}", "below"),
    }
    bands = {
        f"front{n}": (18, by + 2, 33, by + 34, [c(0), c(1), r(0)]),
        f"int1{n}":  (23, by + 25, 47, by + 50,
                      [r(1), r(2), r(3), c(2), r(11), r(12)]),
        f"int2{n}":  (45, by + 2, 57, by + 30, [r(4), r(5), r(6), r(7), c(3)]),
        f"int3{n}":  (71, by + 2, 83, by + 30, [r(8), r(9), r(10), c(4)]),
        f"quant{n}": (97, by + 2, 109, by + 30,
                      [r(13), r(14), r(15), r(16), r(17)]),
    }
    return anchors, decouple, bands


ANCHORS = {
    # digital, top right, beside the socket: the clock is made along the top
    # row, the data path runs down towards the socket's I2S pins
    "Y1": (127, 12, 0),   "U9": (146, 12, 90), "J1": (162, 12, 0),
    "U3": (131, 34, 90),  "U4": (156, 34, 90),
    "U6": (131, 52, 90),  "U8": (156, 52, 90),
    # the 5 V inlet: bead beside the socket's 5 V pins, reservoir after it
    "FB1": (126, 66, 0),  "C1": (140, 68, 0),  "C2": (152, 66, 0),
    # power, bottom right: pump down the right-hand column, reference left
    "U1": (129, 82, 90),  "C4": (152, 80, 0),  "D1": (163, 80, 90),
    "D2": (163, 98, 90),  "C5": (152, 94, 0),  "R1": (152, 104, 0),
    "C6": (152, 112, 0),  "U2": (123, 104, 90),
}
DECOUPLE = {
    "C3": ("U1", "above"), "C7": ("U2", "above"), "C8": ("U2", "below"),
}
BANDS = {
    "pierce": (121, 19, 168, 28, ["R10", "R11", "C16", "C17", "C9"]),
    "clk":    (121, 41, 168, 46, ["C10", "C11", "R12", "R13"]),
    "pi":     (121, 58, 162, 63, ["C13", "C15"]),
    "ref":    (131, 92, 145, 114, ["R2", "R3", "R4", "R5"]),
}
for n, by in ((20, 4), (60, 60)):
    a, d, b = channel(n, by)
    ANCHORS.update(a)
    DECOUPLE.update(d)
    BANDS.update(b)


def load_fp(fpid):
    lib, name = fpid.split(":")
    for base in FPLIBS:
        d = os.path.join(base, f"{lib}.pretty")
        if os.path.isdir(d):
            fp = pcbnew.FootprintLoad(d, name)
            if fp is not None:
                return fp
    raise SystemExit(f"footprint not found: {fpid}")


def pad_mm(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == num:
            return (round(ToMM(p.GetPosition().x), 3),
                    round(ToMM(p.GetPosition().y), 3))
    raise SystemExit(f"{fp.GetReference()} has no pad {num}")


def place_pi_socket(fp):
    """Back side, oriented so pin 1/2/39 land where the Pi's header is."""
    try:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LeftRight)
    except AttributeError:
        fp.Flip(fp.GetPosition(), False)
    want2 = (round(PI_PIN2[0] - PI_PIN1[0], 2), round(PI_PIN2[1] - PI_PIN1[1], 2))
    want39 = (round(PI_PIN39[0] - PI_PIN1[0], 2), round(PI_PIN39[1] - PI_PIN1[1], 2))
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(VECTOR2I(0, 0))
        p1, p2, p39 = pad_mm(fp, "1"), pad_mm(fp, "2"), pad_mm(fp, "39")
        d2 = (round(p2[0] - p1[0], 2), round(p2[1] - p1[1], 2))
        d39 = (round(p39[0] - p1[0], 2), round(p39[1] - p1[1], 2))
        if d2 == want2 and d39 == want39:
            fp.SetPosition(VECTOR2I(FromMM(PI_PIN1[0] - p1[0]),
                                    FromMM(PI_PIN1[1] - p1[1])))
            fp.SetLocked(True)
            got = pad_mm(fp, "1")
            assert (round(got[0], 2), round(got[1], 2)) == \
                (round(PI_PIN1[0], 2), round(PI_PIN1[1], 2)), got
            return rot
    raise SystemExit("could not orient the Pi socket")


def add_hole(board, ref, fpname, x, y):
    fp = load_fp(f"MountingHole:{fpname}")
    fp.SetReference(ref)
    fp.SetValue(fpname)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)
    fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    fp.SetLocked(True)
    return fp


def add_zone(board, net, layer, x0, y0, x1, y1, priority=0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(priority)
    z.SetIsFilled(True)
    z.SetLocalClearance(FromMM(0.3))
    z.SetMinThickness(FromMM(0.25))
    # thermal reliefs: every lead is hand-soldered, and a lead into a solid
    # inner plane on a 1.6 mm four-layer board sinks a 40 W iron
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FromMM(0.4))
    z.SetThermalReliefSpokeWidth(FromMM(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(FromMM(x), FromMM(y))
    board.Add(z)
    return z


def write_project(outf, netnames):
    """Netclasses into the .kicad_pro: KiCad and FreeRouting both read them."""
    prof = os.path.splitext(outf)[0] + ".kicad_pro"
    doc = {}
    if os.path.exists(prof):
        with open(prof, encoding="utf-8") as f:
            doc = json.load(f)
    r = RULES
    base = {"bus_width": 12.0, "wire_width": 6.0, "line_style": 0,
            "schematic_color": "rgba(0, 0, 0, 0.000)",
            "pcb_color": "rgba(0, 0, 0, 0.000)",
            "via_diameter": r["via"], "via_drill": r["via_drill"],
            "clearance": r["clearance"], "microvia_diameter": 0.3,
            "microvia_drill": 0.1, "diff_pair_width": 0.3,
            "diff_pair_gap": 0.2, "diff_pair_via_gap": 0.25}
    ns = doc.setdefault("net_settings", {})
    ns["meta"] = {"version": 4}
    ns["classes"] = [dict(base, name="Default", track_width=r["track"]),
                     dict(base, name="Supply", track_width=r["supply_track"])]
    ns["netclass_patterns"] = [{"netclass": "Supply", "pattern": n}
                               for n in SUPPLY_NETS if n in netnames]
    ns["netclass_assignments"] = {n: "Supply" for n in SUPPLY_NETS
                                  if n in netnames}
    rules = doc.setdefault("board", {}).setdefault("design_settings", {}) \
               .setdefault("rules", {})
    rules.update({"min_clearance": r["clearance"], "min_track_width": 0.2,
                  "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
                  "min_copper_edge_clearance": r["edge"],
                  "min_via_annular_width": 0.15})
    doc["meta"] = {"filename": os.path.basename(prof), "version": 3}
    with open(prof, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def main(jsonf, outf):
    data = json.load(open(jsonf, encoding="utf-8"))
    board = pcbnew.NewBoard(outf)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ds.m_TrackMinWidth = FromMM(0.2)
    ds.m_ViasMinSize = FromMM(0.5)
    ds.m_MinThroughDrill = FromMM(0.3)
    ds.m_MinClearance = FromMM(RULES["clearance"])
    ds.m_CopperEdgeClearance = FromMM(RULES["edge"])
    ds.m_ViasMinAnnularWidth = FromMM(0.15)
    nc = board.GetAllNetClasses()["Default"]
    nc.SetTrackWidth(FromMM(RULES["track"]))
    nc.SetClearance(FromMM(RULES["clearance"]))
    nc.SetViaDiameter(FromMM(RULES["via"]))
    nc.SetViaDrill(FromMM(RULES["via_drill"]))

    netmap = {}
    for name in data["nets"]:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netmap[name] = ni

    fps = {}
    for c in data["components"]:
        fp = load_fp(c["footprint"])
        fp.SetReference(c["ref"])
        fp.SetValue(c["value"] or "")
        board.Add(fp)
        for pad in fp.Pads():
            net = c["pads"].get(pad.GetNumber())
            if net:
                pad.SetNet(netmap[net])
        if c["pads"] and all(p.GetNetCode() == 0 for p in fp.Pads()):
            raise SystemExit(f"{c['ref']}: no pad got a net")
        fps[c["ref"]] = fp

    # outline
    rect = pcbnew.PCB_SHAPE(board)
    rect.SetShape(pcbnew.SHAPE_T_RECT)
    rect.SetStart(VECTOR2I(0, 0))
    rect.SetEnd(VECTOR2I(FromMM(W), FromMM(H)))
    rect.SetLayer(pcbnew.Edge_Cuts)
    rect.SetWidth(FromMM(0.1))
    rect.SetFilled(False)
    board.Add(rect)

    # holes: four M3 for the board, four M2.5 for the Pi
    for i, (x, y) in enumerate(BOARD_HOLES, 1):
        add_hole(board, f"H{i}", "MountingHole_3.2mm_M3", x, y)
    for i, (x, y) in enumerate(PI_HOLES, 5):
        add_hole(board, f"H{i}", "MountingHole_2.7mm_M2.5", x, y)

    # the Pi socket, copper side
    rot = place_pi_socket(fps["J2"])
    # its reference would otherwise sit on its own pads on the back silk
    fps["J2"].Reference().SetPosition(VECTOR2I(FromMM(PI_HDR[0]),
                                               FromMM(PI_HDR[1] + 29)))
    print(f"J2 on B.Cu at rot {rot}, pin 1 {pad_mm(fps['J2'], '1')}, "
          f"pin 40 {pad_mm(fps['J2'], '40')}")

    # floorplan
    FP.GAP = 1.5
    FP.AXIAL_VERTICAL = False
    placed, taken = [], []

    def claim(fp):
        x0, y0, x1, y1 = FP.box(fp)
        taken.append((x0 - FP.GAP / 2, y0 - FP.GAP / 2,
                      x1 + FP.GAP / 2, y1 + FP.GAP / 2))

    claim(fps["J2"])
    for fp in board.GetFootprints():
        if fp.GetReference().startswith("H"):
            claim(fp)
    for ref, (x, y, r) in ANCHORS.items():
        FP.place(fps[ref], x, y, r)
        claim(fps[ref])
        placed.append(ref)
    for cap, (host, side) in DECOUPLE.items():
        fp, hostfp = fps[cap], fps[host]
        r = 90 if side in ("left", "right") else 0
        cw, ch = FP.size_mm(fp, r)
        hx0, hy0, hx1, hy1 = FP.box(hostfp)
        hcx, hcy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
        dy = (hy1 - hy0 + ch) / 2 + FP.GAP
        dx = (hx1 - hx0 + cw) / 2 + FP.GAP
        pos = {"above": (hcx, hcy - dy), "below": (hcx, hcy + dy),
               "left": (hcx - dx, hcy), "right": (hcx + dx, hcy)}[side]
        FP.place(fp, pos[0], pos[1], r)
        claim(fp)
        placed.append(cap)
    for name, (x0, y0, x1, y1, refs) in BANDS.items():
        FP.pack(board, name, (x0, y0, x1, y1), refs, placed, taken)
    left = sorted(r for r in fps if r not in placed and r != "J2")
    if left:
        raise SystemExit(f"unplaced: {left}")

    # everything inside the outline?
    for fp in board.GetFootprints():
        x0, y0, x1, y1 = FP.box(fp)
        if x0 < 0.5 or y0 < 0.5 or x1 > W - 0.5 or y1 > H - 0.5:
            print(f"   WARNING {fp.GetReference()} reaches the edge: "
                  f"({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f})")

    # planes
    add_zone(board, netmap["GND"], pcbnew.In1_Cu, 0.5, 0.5, W - 0.5, H - 0.5)
    add_zone(board, netmap["+5V"], pcbnew.In2_Cu, 0.5, 0.5, W - 0.5, H - 0.5)

    t = pcbnew.PCB_TEXT(board)
    t.SetText("VINYL ADC  rev C  4-layer")
    t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(VECTOR2I(FromMM(60), FromMM(117)))
    t.SetTextSize(VECTOR2I(FromMM(2), FromMM(2)))
    board.Add(t)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(outf, board)
    write_project(outf, set(data["nets"]))
    print(f"wrote {outf}: {len(fps)} parts + 8 holes, {W:.0f} x {H:.0f} mm, "
          f"4 layers, {len(placed)} placed")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
