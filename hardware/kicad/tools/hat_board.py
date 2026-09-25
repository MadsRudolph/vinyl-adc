#!/usr/bin/env python3
r"""Build one HAT board (rev D through-hole, rev E SMD) from its netlist and
a floorplan spec, with hat_place doing the placement.

    python3 tools/hat_board.py rev_e <netlist.json> <out.kicad_pcb> [--seed N]
    python3 tools/hat_board.py rev_d ...
    python3 tools/hat_board.py rev_e --silk <routed.kicad_pcb>   (legends only)

The spec module (`tools/<rev>_floor.py`) owns everything particular to a
board: outline, the Pi's position, anchors, regions, twins, decoupling
hosts, the In2 split and the legends.  This file owns what both share: the
Pi socket's orientation search, holes, netclasses and rules, planes, the
reference-text pass and the checks that every plane pad sits in its own
plane.
"""
import argparse
import importlib
import json
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hat_place as HP                                        # noqa: E402

if not hasattr(pcbnew.SwigPyIterator, "next"):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__

# the floorplan modules `import hat_board`; run as a script this file is
# __main__, and without this they would get a second copy whose LEGENDS
# list the reference pass never sees
sys.modules.setdefault("hat_board", sys.modules[__name__])


FPLIBS = [os.path.join(HERE, "..", "lib"), "/usr/share/kicad/footprints",
          r"C:\Program Files\KiCad\10.0\share\kicad\footprints"]

SUPPLY_NETS = ("-5V", "+3V3", "PUMP", "VREF_P", "VREF_N", "PI_5V", "+5V",
               "+5VA", "TH_P", "TH_N")

CLOCK_NETS = ("CLK6M", "MCLK", "MCLK_SRC", "BCLK", "LRCLK", "DIN",
              "PI_BCLK", "PI_LRCLK", "PI_DIN", "GPCLK0")


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


def add_zone(board, net, layer, pts, priority=0):
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
    for x, y in pts:
        o.Append(FromMM(x), FromMM(y))
    board.Add(z)
    return z


def add_text(board, text, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0,
             thickness=None, mirror=False):
    size = max(size, 0.8)          # KiCad's (and the fab's) silk minimum
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thickness or max(0.12, size * 0.15)))
    t.SetTextAngleDegrees(rot)
    if mirror:
        t.SetMirrored(True)
    board.Add(t)
    return t


def write_project(outf, netnames, r):
    """Netclasses into the .kicad_pro: KiCad and FreeRouting both read them."""
    prof = os.path.splitext(outf)[0] + ".kicad_pro"
    doc = {}
    if os.path.exists(prof):
        with open(prof, encoding="utf-8") as f:
            doc = json.load(f)
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
                     dict(base, name="Supply", track_width=r["supply_track"]),
                     dict(base, name="Clock", track_width=r["clock_track"])]
    pats = [{"netclass": "Supply", "pattern": n} for n in SUPPLY_NETS
            if n in netnames]
    pats += [{"netclass": "Clock", "pattern": n} for n in CLOCK_NETS
             if n in netnames]
    ns["netclass_patterns"] = pats
    assign = {n: "Supply" for n in SUPPLY_NETS if n in netnames}
    assign.update({n: "Clock" for n in CLOCK_NETS if n in netnames})
    ns["netclass_assignments"] = assign
    rules = doc.setdefault("board", {}).setdefault("design_settings", {}) \
               .setdefault("rules", {})
    rules.update({"min_clearance": r["clearance"], "min_track_width": 0.2,
                  "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
                  "min_copper_edge_clearance": r["edge"],
                  "min_via_annular_width": 0.15, "min_hole_clearance": 0.25,
                  "min_hole_to_hole": 0.25, "solder_mask_clearance": 0.0,
                  "solder_mask_min_width": 0.0})
    doc["meta"] = {"filename": os.path.basename(prof), "version": 3}
    with open(prof, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)



# -- the Raspberry Pi, seen from above the board ------------------------------
# Header centred on the near hole line, holes 29 mm either side of it, far
# holes 49 mm away (verified against KiCad's Raspberry_Pi_Zero_Socketed
# footprint and its HAT template).  Long axis up the board: SD end at
# hdr_y + 32.5, USB/Ethernet end 20 mm over the top edge.  Seen from above,
# pin 1 (3V3) is the INBOARD row at the SD end and pin 2 (5V) the row along
# the Pi's edge; only that orientation lets a socket on the copper side land
# pins 1, 2 and 39 on the Pi's pins, and place_pi_socket() checks it.
def pi_geometry(hx, hy):
    return dict(
        hdr=(hx, hy),
        holes=[(hx, hy - 29), (hx + 49, hy - 29), (hx, hy + 29),
               (hx + 49, hy + 29)],
        pin1=(hx + 1.27, hy + 24.13), pin2=(hx - 1.27, hy + 24.13),
        pin39=(hx + 1.27, hy - 24.13))


def place_pi_socket(fp, pi):
    """Back side, oriented so pins 1/2/39 land where the Pi's header is."""
    try:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LeftRight)
    except AttributeError:
        fp.Flip(fp.GetPosition(), False)
    p1w, p2w, p39w = pi["pin1"], pi["pin2"], pi["pin39"]
    want2 = (round(p2w[0] - p1w[0], 2), round(p2w[1] - p1w[1], 2))
    want39 = (round(p39w[0] - p1w[0], 2), round(p39w[1] - p1w[1], 2))
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(VECTOR2I(0, 0))
        p1, p2, p39 = pad_mm(fp, "1"), pad_mm(fp, "2"), pad_mm(fp, "39")
        d2 = (round(p2[0] - p1[0], 2), round(p2[1] - p1[1], 2))
        d39 = (round(p39[0] - p1[0], 2), round(p39[1] - p1[1], 2))
        if d2 == want2 and d39 == want39:
            fp.SetPosition(VECTOR2I(FromMM(p1w[0] - p1[0]),
                                    FromMM(p1w[1] - p1[1])))
            fp.SetLocked(True)
            got = pad_mm(fp, "1")
            assert (round(got[0], 2), round(got[1], 2)) == \
                (round(p1w[0], 2), round(p1w[1], 2)), got
            return rot
    raise SystemExit("could not orient the Pi socket")


def _abs_box(fp):
    bb = fp.GetBoundingBox(False, False)
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
            ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


# -- reference designators -----------------------------------------------------
def place_refs(board, fps, size, keep_out=()):
    """Every reference on the silk beside its part, touching nothing.

    Candidates round the courtyard -- above, below, left, right, at the
    part's own orientation and turned 90 -- are tried in turn against every
    pad, every courtyard and every text already down.  A part with no free
    spot gets its reference on F.Fab only (the assembly drawing still has
    it); the count is printed so it is a number, not a surprise.
    """
    eb = board.GetBoardEdgesBoundingBox()
    EW, EH = ToMM(eb.GetRight()), ToMM(eb.GetBottom())
    pads, texts = [], list(keep_out)
    for fp in fps.values():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            pads.append((ToMM(bb.GetLeft()) - 0.2, ToMM(bb.GetTop()) - 0.2,
                         ToMM(bb.GetRight()) + 0.2, ToMM(bb.GetBottom()) + 0.2))
    bodies = {}
    for ref, fp in fps.items():
        if fp.GetLayer() == pcbnew.B_Cu:
            continue
        bodies[ref] = _courtyard(fp)

    def hit(b, own):
        x0, y0, x1, y1 = b
        for a in pads:
            if x0 < a[2] and a[0] < x1 and y0 < a[3] and a[1] < y1:
                return True
        for a in texts:
            if x0 < a[2] and a[0] < x1 and y0 < a[3] and a[1] < y1:
                return True
        for r, a in bodies.items():
            if r == own:
                continue
            if x0 < a[2] and a[0] < x1 and y0 < a[3] and a[1] < y1:
                return True
        return False

    hidden = []
    order = sorted(fps, key=lambda r: -((bodies.get(r, (0, 0, 0, 0))[2]
                                         - bodies.get(r, (0, 0, 0, 0))[0])))
    for ref in order:
        fp = fps[ref]
        if fp.GetLayer() == pcbnew.B_Cu or ref.startswith("H"):
            continue
        t = fp.Reference()
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(max(0.12, size * 0.15)))
        n = len(ref)
        tw, th = n * size * 0.9 + 0.3, size + 0.4
        x0, y0, x1, y1 = bodies[ref]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cands = []
        for ang in (0, 90):
            w, h = (tw, th) if ang == 0 else (th, tw)
            cands += [(cx, y0 - h / 2 - 0.1, ang, w, h),
                      (cx, y1 + h / 2 + 0.1, ang, w, h),
                      (x0 - w / 2 - 0.1, cy, ang, w, h),
                      (x1 + w / 2 + 0.1, cy, ang, w, h)]
        # inside the courtyard, over the body, for ICs and other big parts;
        # a small part's body would hide its own reference
        big = (x1 - x0) * (y1 - y0) > 60 and ref[0] in "UYL"
        if big and (x1 - x0) > tw + 1 and (y1 - y0) > th + 1:
            cands.insert(0, (cx, cy, 0, tw, th))
        elif big and (y1 - y0) > tw + 1 and (x1 - x0) > th + 1:
            cands.insert(0, (cx, cy, 90, th, tw))
        done = False
        for x, y, ang, w, h in cands:
            b = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            inside = (b[0] > x0 and b[2] < x1 and b[1] > y0 and b[3] < y1)
            if hit(b, ref if inside else None):
                continue
            if b[0] < 0.3 or b[1] < 0.3 or b[2] > EW - 0.3 or b[3] > EH - 0.3:
                continue
            t.SetLayer(pcbnew.F_SilkS)
            t.SetVisible(True)
            t.SetTextAngleDegrees(ang)
            t.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
            t.SetKeepUpright(True)
            texts.append(b)
            done = True
            break
        if not done:
            t.SetLayer(pcbnew.F_Fab)
            t.SetPosition(VECTOR2I(FromMM(cx), FromMM(cy)))
            hidden.append(ref)
    return hidden


def _courtyard(fp):
    return HP._bbox_mm(fp)             # absolute: the footprint is placed


LEGENDS = []                  # boxes of the legends, kept clear of references


def add_board_text(board, text, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0,
                   mirror=False):
    t = add_text(board, text, x, y, size=size, layer=layer, rot=rot,
                 mirror=mirror)
    if layer == pcbnew.F_SilkS:
        w, h = len(text) * max(size, 0.8) * 0.9 + 0.3, max(size, 0.8) + 0.4
        if rot in (90, 270):
            w, h = h, w
        LEGENDS.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    return t


def text_block(board, fps, lines, sizes, layer, region, mirror=False,
               step=0.5):
    """Put a block of legend lines where no pad reaches, inside `region`.

    The copper side of a through-hole board is mostly pads; a title at a
    fixed spot lands on some of them (silk over copper), so the spot is
    searched for instead: the first place, scanning the region, where the
    block's box clears every pad on that side by 0.4 mm.
    """
    side_cu = pcbnew.B_Cu if layer == pcbnew.B_SilkS else pcbnew.F_Cu
    pads = []
    for fp in fps.values():
        for p in fp.Pads():
            if p.IsOnLayer(side_cu):
                bb = p.GetBoundingBox()
                pads.append((ToMM(bb.GetLeft()) - 0.4, ToMM(bb.GetTop()) - 0.4,
                             ToMM(bb.GetRight()) + 0.4, ToMM(bb.GetBottom()) + 0.4))
    pitch = [s * 1.9 for s in sizes]
    w = max(len(t) * s * 0.9 for t, s in zip(lines, sizes)) + 0.4
    h = sum(pitch)
    x0, y0, x1, y1 = region
    y = y0
    while y + h <= y1:
        x = x0
        while x + w <= x1:
            box = (x, y, x + w, y + h)
            if not any(box[0] < a[2] and a[0] < box[2] and box[1] < a[3]
                       and a[1] < box[3] for a in pads):
                cy = y
                for t, s, pt in zip(lines, sizes, pitch):
                    add_board_text(board, t, x + w / 2, cy + pt / 2, size=s,
                                   layer=layer, mirror=mirror)
                    cy += pt
                return (x + w / 2, y + h / 2)
            x += step
        y += step
    print(f"   no pad-free spot for '{lines[0]}' in {region}; left off")
    return None


def build(spec, jsonf, outf, seed=1, iters=None):
    data = json.load(open(jsonf, encoding="utf-8"))
    board = pcbnew.NewBoard(outf)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    R = spec.RULES
    ds.m_TrackMinWidth = FromMM(0.15)
    ds.m_ViasMinSize = FromMM(0.45)
    ds.m_MinThroughDrill = FromMM(0.25)
    ds.m_MinClearance = FromMM(R["clearance"])
    ds.m_CopperEdgeClearance = FromMM(R["edge"])
    ds.m_ViasMinAnnularWidth = FromMM(0.1)
    nc = board.GetAllNetClasses()["Default"]
    nc.SetTrackWidth(FromMM(R["track"]))
    nc.SetClearance(FromMM(R["clearance"]))
    nc.SetViaDiameter(FromMM(R["via"]))
    nc.SetViaDrill(FromMM(R["via_drill"]))

    netmap = {}
    for name in data["nets"]:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netmap[name] = ni
    _netclasses(board, netmap, R)

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
        fps[c["ref"]] = fp

    W, H = spec.W, spec.H
    rect = pcbnew.PCB_SHAPE(board)
    rect.SetShape(pcbnew.SHAPE_T_RECT)
    rect.SetStart(VECTOR2I(0, 0))
    rect.SetEnd(VECTOR2I(FromMM(W), FromMM(H)))
    rect.SetLayer(pcbnew.Edge_Cuts)
    rect.SetWidth(FromMM(0.1))
    rect.SetFilled(False)
    board.Add(rect)

    pi = pi_geometry(*spec.PI_HDR)
    holes = []
    for i, (x, y) in enumerate(spec.BOARD_HOLES, 1):
        holes.append(add_hole(board, f"H{i}", "MountingHole_3.2mm_M3", x, y))
    for i, (x, y) in enumerate(pi["holes"], len(spec.BOARD_HOLES) + 1):
        holes.append(add_hole(board, f"H{i}", "MountingHole_2.7mm_M2.5", x, y))

    rot = place_pi_socket(fps["J2"], pi)
    print(f"  J2 on B.Cu at rot {rot}, pin 1 {pad_mm(fps['J2'], '1')}")

    placer_fps = {r: f for r, f in fps.items() if r != "J2"}
    P = HP.Placer(placer_fps, W, H, gap=spec.GAP, margin=spec.MARGIN,
                  snap=spec.SNAP, weights=spec.WEIGHTS, seed=seed)
    # the Pi socket's through pads, the holes (with a standoff's washer) and
    # anything the spec reserves
    x0, y0, x1, y1 = _abs_box(fps["J2"])
    P.obstacle((x0 - 0.3, y0 - 0.3, x1 + 0.3, y1 + 0.3))
    for (x, y), rad in ([(h, 3.3) for h in spec.BOARD_HOLES]
                        + [(h, 3.0) for h in pi["holes"]]):
        P.obstacle((x - rad, y - rad, x + rad, y + rad))
    for b in getattr(spec, "KEEPOUTS", ()):
        P.obstacle(b)
    P.plane_at = spec.plane_at
    spec.configure(P)
    clash = P.check_fixed()
    if clash:
        for c in clash:
            print("   FIXED CLASH", c)
        raise SystemExit("anchors collide; fix the spec")
    P.greedy()
    print(f"  greedy: cost {P.total():.0f}")
    P.anneal(iters or spec.ITERS)
    moved = P.tidy()
    print(f"  tidy: {moved} parts aligned; cost {P.total():.0f}")
    P.report()
    P.apply()

    for net, layer, pts in spec.zones(W, H):
        add_zone(board, netmap[net], layer, pts)
    _check_planes(spec, fps)

    LEGENDS.clear()
    spec.silkscreen(board, fps)
    hidden = place_refs(board, fps, spec.REF_SIZE, keep_out=LEGENDS)
    print(f"  references: {len(hidden)} moved to F.Fab (no free spot): "
          + " ".join(sorted(hidden)))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(outf, board)
    _write_project(outf, set(data["nets"]), R)
    print(f"wrote {outf}: {len(fps)} parts, {W:.0f} x {H:.0f} mm, 4 layers")


def _check_planes(spec, fps):
    bad = 0
    for ref, fp in fps.items():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net not in ("+5V", "+5VA"):
                continue
            x, y = ToMM(pad.GetPosition().x), ToMM(pad.GetPosition().y)
            if spec.plane_at(x, y) != net:
                bad += 1
                print(f"   WARNING {ref} pad {pad.GetNumber()} ({net}) at "
                      f"({x:.1f},{y:.1f}) is outside its plane")
    if not bad:
        print("  planes: every +5V / +5VA pad sits in its own plane")


def _netclasses(board, netmap, R):
    ncs = board.GetAllNetClasses()
    for name, width in (("Supply", R["supply_track"]),
                        ("Clock", R["clock_track"])):
        if name not in ncs:
            ncs[name] = pcbnew.NETCLASS(name)
        nc = ncs[name]
        nc.SetTrackWidth(FromMM(width))
        nc.SetClearance(FromMM(R["clearance"]))
        nc.SetViaDiameter(FromMM(R["via"]))
        nc.SetViaDrill(FromMM(R["via_drill"]))
    for name, ni in netmap.items():
        if name in SUPPLY_NETS:
            ni.SetNetClass(ncs["Supply"])
        elif name in CLOCK_NETS:
            ni.SetNetClass(ncs["Clock"])


def _write_project(outf, netnames, R):
    write_project(outf, netnames, R)
    prof = os.path.splitext(outf)[0] + ".kicad_pro"
    doc = json.load(open(prof, encoding="utf-8"))
    rules = doc["board"]["design_settings"]["rules"]
    rules.update({"min_track_width": 0.15, "min_via_diameter": 0.45,
                  "min_through_hole_diameter": 0.25,
                  "min_via_annular_width": 0.1,
                  # a DIP's GND pin between two neighbours can grow only one
                  # thermal spoke into an inner plane (the other side is the
                  # neighbour's clearance); one 0.5 mm spoke carries far more
                  # than a logic ground needs, and a solid connection would
                  # sink a hand iron
                  "min_resolved_spokes": 1})
    json.dump(doc, open(prof, "w", encoding="utf-8"), indent=2)


def resilk(spec, pcbf):
    board = pcbnew.LoadBoard(pcbf)
    for d in list(board.GetDrawings()):
        if isinstance(d, pcbnew.PCB_TEXT) and \
                d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            board.Delete(d)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    LEGENDS.clear()
    spec.silkscreen(board, fps)
    hidden = place_refs(board, fps, spec.REF_SIZE, keep_out=LEGENDS)
    print(f"  references: {len(hidden)} on F.Fab only")
    pcbnew.SaveBoard(pcbf, board)
    print(f"re-silked {pcbf}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rev")
    ap.add_argument("args", nargs="+")
    ap.add_argument("--silk", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--iters", type=int, default=None)
    a = ap.parse_args()
    spec = importlib.import_module(f"{a.rev}_floor")
    if a.silk:
        resilk(spec, a.args[0])
    else:
        build(spec, a.args[0], a.args[1], seed=a.seed, iters=a.iters)


if __name__ == "__main__":
    main()
