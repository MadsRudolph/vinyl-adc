#!/usr/bin/env python3
r"""Fan every SMD plane pad out to its inner plane: one short stub, one via.

    python3 tools/fanout.py board.kicad_pcb [--nets GND,+5V,+5VA]
                            [--via 0.6 --drill 0.3 --width 0.4 --clear 0.2]

FreeRouting counts a plane net as connected wherever a THROUGH-hole pad
meets the plane, and never drops a via for a surface pad on its own, so
on an SMD board every GND, +5V and +5VA pad would come back unconnected.
This is the job a hand layout does first anyway: each decoupling cap's
pads and each IC ground pin get their own via, as close as clearance
allows, before any signal is routed.

The via goes OUTWARD: away from the part's centre for an IC pin, away from
the other pad for a two-pad part, so it never lands between the pads of
its own component.  Candidates walk out from the pad edge in 0.2 mm steps
in eight directions; the first that clears every other-net pad, every via
already placed and the board edge by `--clear` (and whose stub clears them
too) wins.  Stubs and vias are LOCKED, which KiCad exports to the DSN as
protected wiring: the router routes round them and never rips them up.
A pad with no legal spot is printed, not skipped silently.

    python3 tools/fanout.py board.kicad_pcb --islands board.drc.json

is for AFTER routing, which on the SMD board is the only order that works:
FreeRouting 2.4.1 throws a NullPointerException in its router, and never
returns, on a board that already carries any copper.  So: route, then run
this without --islands (every SMD plane pad gets its via where the routed
copper leaves room -- the decoupling practice a hand layout starts with),
then run DRC and call it again with --islands.  A plane "island" is a
group of plane-net pads FreeRouting joined with tracks on a signal layer
and never took to the plane; DRC lists each one as unconnected.  Where
none of its pads had room for a stub, a via dropped straight onto one of
its own tracks joins it to the plane.
"""
import json
import re
import argparse
import math
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

if not hasattr(pcbnew.SwigPyIterator, "next"):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__


def rect_dist(px, py, r):
    """Distance from a point to an axis-aligned rectangle (0 inside)."""
    x0, y0, x1, y1 = r
    dx = max(x0 - px, 0, px - x1)
    dy = max(y0 - py, 0, py - y1)
    return math.hypot(dx, dy)


def seg_rect_dist(ax, ay, bx, by, r, n=8):
    return min(rect_dist(ax + (bx - ax) * t / n, ay + (by - ay) * t / n, r)
               for t in range(n + 1))


def seg_seg_dist(a, b, c, d, n=10):
    """Minimum distance between segments ab and cd (sampled on ab)."""
    best = 1e9
    for t in range(n + 1):
        px = a[0] + (b[0] - a[0]) * t / n
        py = a[1] + (b[1] - a[1]) * t / n
        best = min(best, pt_seg_dist(px, py, c, d))
    return best


def pt_seg_dist(px, py, c, d):
    vx, vy = d[0] - c[0], d[1] - c[1]
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - c[0]) * vx + (py - c[1]) * vy) / L))
    return math.hypot(px - (c[0] + t * vx), py - (c[1] + t * vy))


def island_items(drc_json, nets):
    """UUIDs, and (ref, pad) of SMD pads, of every plane-net item in the
    DRC's unconnected list."""
    uu, pads = set(), set()
    d = json.load(open(drc_json, encoding="utf-8"))
    for u in d.get("unconnected_items", []):
        for it in u["items"]:
            m = re.search(r"\[([^\]]+)\]", it["description"])
            if m and m.group(1) in nets:
                uu.add(it["uuid"])
            m = re.match(r"Pad (\S+) \[([^\]]+)\] of (\S+)", it["description"])
            if m and m.group(2) in nets:
                pads.add((m.group(3), m.group(1)))
    return uu, pads


def via_on_tracks(board, uuids, via_d, drill, clear, edge):
    """One via on a track of each listed island, where it clears the rest."""
    bb = board.GetBoardEdgesBoundingBox()
    X0, Y0 = ToMM(bb.GetLeft()), ToMM(bb.GetTop())
    X1, Y1 = ToMM(bb.GetRight()), ToMM(bb.GetBottom())
    vr = via_d / 2
    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            b = p.GetBoundingBox()
            pads.append((p.GetNetname(), (ToMM(b.GetLeft()), ToMM(b.GetTop()),
                                          ToMM(b.GetRight()), ToMM(b.GetBottom())),
                         p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH))
    tracks = list(board.GetTracks())
    segs, vias = [], []
    for t in tracks:
        if t.GetClass() == "PCB_VIA":
            vias.append((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)))
        else:
            segs.append(((ToMM(t.GetStart().x), ToMM(t.GetStart().y)),
                         (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)),
                         ToMM(t.GetWidth()) / 2, t.GetNetname()))
    done = 0
    for t in tracks:
        if t.GetClass() == "PCB_VIA" or t.m_Uuid.AsString() not in uuids:
            continue
        net = t.GetNetname()
        a = (ToMM(t.GetStart().x), ToMM(t.GetStart().y))
        b = (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.2))
        for k in range(n + 1):
            vx = a[0] + (b[0] - a[0]) * k / n
            vy = a[1] + (b[1] - a[1]) * k / n
            if (vx - vr < X0 + edge or vy - vr < Y0 + edge
                    or vx + vr > X1 - edge or vy + vr > Y1 - edge):
                continue
            if any(rect_dist(vx, vy, r) < clear + vr for q, r, pth in pads
                   if q != net or pth):
                continue
            if any(math.hypot(x - vx, y - vy) < via_d + clear for x, y in vias):
                continue
            if any(q != net and pt_seg_dist(vx, vy, sa, sb) < vr + hw + clear
                   for sa, sb, hw, q in segs):
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy)))
            v.SetWidth(FromMM(via_d))
            v.SetDrill(FromMM(drill))
            v.SetNet(t.GetNet())
            board.Add(v)
            vias.append((vx, vy))
            done += 1
            break
    return done


def fanout(board, nets, via_d, drill, width, clear, edge, only=None,
           steps=12, compass=8):
    W = ToMM(board.GetBoardEdgesBoundingBox().GetRight())
    H = ToMM(board.GetBoardEdgesBoundingBox().GetBottom())
    X0 = ToMM(board.GetBoardEdgesBoundingBox().GetLeft())
    Y0 = ToMM(board.GetBoardEdgesBoundingBox().GetTop())
    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            pads.append((p, fp, p.GetNetname(),
                         (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
                          ToMM(bb.GetRight()), ToMM(bb.GetBottom()))))
    vias = []            # (x, y, net)
    segs = []            # (a, b, half width, layer, net) of routed copper
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias.append((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y),
                         t.GetNetname()))
        else:
            segs.append(((ToMM(t.GetStart().x), ToMM(t.GetStart().y)),
                         (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)),
                         ToMM(t.GetWidth()) / 2, t.GetLayer(), t.GetNetname()))
    netinfo = board.GetNetsByName()
    placed = failed = 0
    vr = via_d / 2
    targets = [(p, fp, net, r) for p, fp, net, r in pads
               if net in nets and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
               and p.IsOnLayer(pcbnew.F_Cu)
               and (only is None or (fp.GetReference(), p.GetNumber()) in only)]
    for p, fp, net, r in targets:
        cx, cy = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        fx, fy = ToMM(fp.GetPosition().x), ToMM(fp.GetPosition().y)
        own = [q for q in fp.Pads() if q.GetNumber() != p.GetNumber()]
        if len(own) == 1:                # two-pad part: away from the other
            ox, oy = ToMM(own[0].GetPosition().x), ToMM(own[0].GetPosition().y)
            ux, uy = cx - ox, cy - oy
        else:                            # IC: away from the body centre
            ux, uy = cx - fx, cy - fy
        n = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n, uy / n
        # snap the outward direction to the nearest axis first, then try the
        # rest of the compass in order of how far they turn from it
        base = math.atan2(uy, ux)
        axis = round(base / (math.pi / 2)) * (math.pi / 2)
        dirs = sorted({round(axis + k * 2 * math.pi / compass, 6)
                       for k in range(compass)},
                      key=lambda a: abs(math.remainder(a - axis, 2 * math.pi)))
        hw, hh = (r[2] - r[0]) / 2, (r[3] - r[1]) / 2
        best = None
        for a in dirs:
            dx, dy = math.cos(a), math.sin(a)
            reach = abs(dx) * hw + abs(dy) * hh      # pad edge along a
            for step in range(0, steps):
                d = reach + vr + clear * 0.5 + step * 0.2
                vx, vy = cx + dx * d, cy + dy * d
                if (vx - vr < X0 + edge or vy - vr < Y0 + edge
                        or vx + vr > W - edge or vy + vr > H - edge):
                    break
                ok = True
                for q, qfp, qnet, qr in pads:
                    if q is p:
                        continue
                    if qnet == net and qfp is not fp and \
                            q.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
                        continue       # a same-net SMD pad of another part is
                                       # fine; a same-net HOLE is not
                    lim = clear + vr
                    if qnet == net:
                        lim = vr + 0.1
                    if rect_dist(vx, vy, qr) < lim:
                        ok = False
                        break
                    if qnet != net and seg_rect_dist(cx, cy, vx, vy, qr) < \
                            clear + width / 2:
                        ok = False
                        break
                if not ok:
                    continue
                for ax, ay, anet in vias:
                    if math.hypot(ax - vx, ay - vy) < via_d + clear:
                        ok = False
                        break
                for sa, sb, hw2, layer, snet in (segs if ok else ()):
                    if snet == net:
                        continue
                    # the via meets every layer; the stub only F.Cu
                    if pt_seg_dist(vx, vy, sa, sb) < vr + hw2 + clear:
                        ok = False
                        break
                    if layer == pcbnew.F_Cu and seg_seg_dist(
                            (cx, cy), (vx, vy), sa, sb) < width / 2 + hw2 + clear:
                        ok = False
                        break
                if ok:
                    best = (vx, vy)
                    break
            if best:
                break
        if not best:
            failed += 1
            print(f"   no fan-out for {fp.GetReference()}.{p.GetNumber()} ({net})")
            continue
        vx, vy = best
        ni = netinfo[net]
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(VECTOR2I(FromMM(cx), FromMM(cy)))
        tr.SetEnd(VECTOR2I(FromMM(vx), FromMM(vy)))
        tr.SetWidth(FromMM(width))
        tr.SetLayer(pcbnew.F_Cu)
        tr.SetNet(ni)
        tr.SetLocked(True)
        board.Add(tr)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy)))
        v.SetWidth(FromMM(via_d))
        v.SetDrill(FromMM(drill))
        v.SetNet(ni)
        v.SetLocked(True)
        board.Add(v)
        vias.append((vx, vy, net))
        placed += 1
    return placed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcb")
    ap.add_argument("--nets", default="GND,+5V,+5VA")
    ap.add_argument("--via", type=float, default=0.6)
    ap.add_argument("--drill", type=float, default=0.3)
    ap.add_argument("--width", type=float, default=0.4)
    ap.add_argument("--clear", type=float, default=0.2)
    ap.add_argument("--edge", type=float, default=0.5)
    ap.add_argument("--islands", metavar="DRC_JSON", default=None)
    a = ap.parse_args()
    nets = set(a.nets.split(","))
    board = pcbnew.LoadBoard(a.pcb)
    if a.islands:
        uu, lone = island_items(a.islands, nets)
        # the island's own pads first, reaching further than the first pass
        # did, then a via straight onto one of its tracks
        placed, _f = fanout(board, nets, a.via, a.drill, a.width, a.clear,
                            a.edge, only=lone, steps=25, compass=16)
        placed += via_on_tracks(board, uu, a.via, a.drill, a.clear, a.edge)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(a.pcb, board)
        print(f"  islands: {len(uu)} plane items unconnected, {placed} vias "
              "dropped onto their tracks")
        return 0
    placed, failed = fanout(board, nets, a.via, a.drill, a.width, a.clear,
                            a.edge)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(a.pcb, board)
    print(f"  fan-out: {placed} vias, {failed} pads without a spot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
