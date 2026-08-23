#!/usr/bin/env python
r"""Reconnect the bits of a pour that the routing cut off from the rest of it.

    & "C:\Program Files\KiCad\10.0\bin\python.exe" tools\pcb_stitch.py ..\vinyl_adc_analog.kicad_pcb

FreeRouting is told GND is a plane, so it never routes ground -- which is the
whole point, and why ground needs almost no track segments on these boards. It
then lays other nets' tracks whichever way it likes, and **a track plus its
0.85 mm clearance either side is 2.7 mm of no-copper**. Run one across a pour
and the pour is severed there; the only way round is past the end of that
track. Some ground pads end up on an island with no path back at all.

It is specifically the routing that does this: fill the same pour on a board
with no tracks and every pad connects.

So this adds the copper the router should have left room for. For each pad DRC
reports as unconnected, it finds the shortest orthogonal path back to the main
body of the pour, on a 0.25 mm grid with everything that is not on that net
dilated by clearance + half a track width. It is a maze router, not a stub
search, because a stub cannot get round the end of a track and that is exactly
the move required -- an earlier straight-line version of this solved ten pads
out of twenty-five and introduced a crossing doing it.

It only ever ADDS copper on the net the pad already belongs to, so it cannot
change the netlist. Anything it cannot solve is reported, not quietly left.
"""
import json
import os
import subprocess
import sys
import tempfile
from collections import deque

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
CLEARANCE = 0.85         # the cnc fabrication profile
# Narrower than the netclass's 1.0 mm on purpose. Clearance is what the mill
# cares about -- it cuts the GAP, not the track -- and the corridor a stitch
# has to thread is whatever the router left: 0.85 + w + 0.85. At w = 1.0 that
# is 2.7 mm and most islands have no such gap anywhere on their boundary; at
# 0.5 it is 2.2 and they do. Half a millimetre of copper carries one IC's
# ground return several times over.
TRACK_W = 0.5
GRID = 0.25              # mm per cell
ROUNDS = 4               # refill and re-ask DRC between attempts


# --------------------------------------------------------------- geometry --

def poly_of(line):
    return [(ToMM(line.CPoint(k).x), ToMM(line.CPoint(k).y))
            for k in range(line.PointCount())]


def area(poly):
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def regions(board, net):
    """Filled outlines of `net`'s zones on B.Cu, largest first."""
    out = []
    for z in board.Zones():
        if z.GetNetname() != net or not z.IsOnLayer(pcbnew.B_Cu):
            continue
        sp = z.GetFilledPolysList(pcbnew.B_Cu)
        for o in range(sp.OutlineCount()):
            p = poly_of(sp.Outline(o))
            if len(p) >= 3:
                out.append(p)
    out.sort(key=area, reverse=True)
    return out


class Grid:
    """A blocked/free raster of the board, one net's point of view."""

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.w = int((x1 - x0) / GRID) + 1
        self.h = int((y1 - y0) / GRID) + 1
        self.blocked = bytearray(self.w * self.h)
        self.goal = bytearray(self.w * self.h)

    def cell(self, x, y):
        return (int(round((x - self.x0) / GRID)),
                int(round((y - self.y0) / GRID)))

    def mm(self, i, j):
        return self.x0 + i * GRID, self.y0 + j * GRID

    def block_rect(self, x0, y0, x1, y1, r):
        """Mark every cell within `r` mm of an axis-aligned rectangle.

        Pads are rectangles, and modelling one as a circle of radius
        max(w, h)/2 over-blocks it badly: a DIP LongPad is 1.6 mm across the
        row and 2.4 mm along it, so the circle is 0.4 mm too fat in the
        direction that matters and swallows the neighbouring pin on 2.54 mm
        pitch. Every ground pin in a DIP then looks walled in, and the maze
        router reports "no legal path" for pads a track plainly reaches.
        """
        i0, j0 = self.cell(x0 - r, y0 - r)
        i1, j1 = self.cell(x1 + r, y1 + r)
        rr = r * r
        for j in range(max(0, j0), min(self.h, j1 + 1)):
            py = self.y0 + j * GRID
            dy = max(y0 - py, 0.0, py - y1)
            row = j * self.w
            for i in range(max(0, i0), min(self.w, i1 + 1)):
                px = self.x0 + i * GRID
                dx = max(x0 - px, 0.0, px - x1)
                if dx * dx + dy * dy <= rr:
                    self.blocked[row + i] = 1

    def block_seg(self, ax, ay, bx, by, r, mask=None):
        """Mark every cell within `r` mm of segment ab."""
        mask = self.blocked if mask is None else mask
        i0, j0 = self.cell(min(ax, bx) - r, min(ay, by) - r)
        i1, j1 = self.cell(max(ax, bx) + r, max(ay, by) + r)
        vx, vy = bx - ax, by - ay
        L = vx * vx + vy * vy
        rr = r * r
        for j in range(max(0, j0), min(self.h, j1 + 1)):
            py = self.y0 + j * GRID
            row = j * self.w
            for i in range(max(0, i0), min(self.w, i1 + 1)):
                px = self.x0 + i * GRID
                if L == 0:
                    t = 0.0
                else:
                    t = ((px - ax) * vx + (py - ay) * vy) / L
                    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                dx = px - (ax + t * vx)
                dy = py - (ay + t * vy)
                if dx * dx + dy * dy <= rr:
                    mask[row + i] = 1

    def fill_poly(self, poly, mask):
        """Scanline-fill a polygon into `mask`."""
        ys = [p[1] for p in poly]
        j0, j1 = self.cell(0, min(ys))[1], self.cell(0, max(ys))[1]
        for j in range(max(0, j0), min(self.h, j1 + 1)):
            y = self.y0 + j * GRID
            xs = []
            n = len(poly)
            for k in range(n):
                x1, y1 = poly[k]
                x2, y2 = poly[(k + 1) % n]
                if (y1 > y) != (y2 > y):
                    xs.append(x1 + (y - y1) / (y2 - y1) * (x2 - x1))
            xs.sort()
            row = j * self.w
            for a, b in zip(xs[0::2], xs[1::2]):
                ia = max(0, self.cell(a, 0)[0])
                ib = min(self.w - 1, self.cell(b, 0)[0])
                for i in range(ia, ib + 1):
                    mask[row + i] = 1


def build_grid(board, net, bbox):
    """Raster where a track on `net` may legally run, and where it may end."""
    g = Grid(*bbox)
    r = CLEARANCE + TRACK_W / 2.0

    # everything outside the outline (plus its clearance) is blocked
    x0, y0, x1, y1 = bbox
    for j in range(g.h):
        py = g.y0 + j * GRID
        row = j * g.w
        out_y = py < y0 + r or py > y1 - r
        for i in range(g.w):
            px = g.x0 + i * GRID
            if out_y or px < x0 + r or px > x1 - r:
                g.blocked[row + i] = 1

    for t in board.GetTracks():
        if t.GetNetname() == net:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            c = t.GetPosition()
            hw = ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
            g.block_seg(ToMM(c.x), ToMM(c.y), ToMM(c.x), ToMM(c.y), r + hw)
            continue
        if not t.IsOnLayer(pcbnew.B_Cu):
            continue
        a, b = t.GetStart(), t.GetEnd()
        g.block_seg(ToMM(a.x), ToMM(a.y), ToMM(b.x), ToMM(b.y),
                    r + ToMM(t.GetWidth()) / 2)

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                continue
            bb = pad.GetBoundingBox()
            g.block_rect(ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
                         ToMM(bb.GetRight()), ToMM(bb.GetBottom()), r)

    # other nets' pours: their interior AND a clearance ring round the edge
    for other in pour_nets(board):
        if other == net:
            continue
        for poly in regions(board, other):
            g.fill_poly(poly, g.blocked)
            for k in range(len(poly)):
                ax, ay = poly[k]
                bx, by = poly[(k + 1) % len(poly)]
                g.block_seg(ax, ay, bx, by, r)

    # the goal is the MAIN body of this net's pour -- not any island, or the
    # stub lands in a sliver that is just as disconnected as the pad was
    main = regions(board, net)
    if main:
        g.fill_poly(main[0], g.goal)
    return g


def route(g, start, budget=6000000):
    """Breadth-first from `start` to any goal cell. Returns a cell path."""
    si, sj = start
    if not (0 <= si < g.w and 0 <= sj < g.h):
        return None
    w, h = g.w, g.h
    prev = {}
    q = deque([(si, sj)])
    seen = bytearray(w * h)
    seen[sj * w + si] = 1
    steps = 0
    while q and steps < budget:
        i, j = q.popleft()
        steps += 1
        if g.goal[j * w + i]:
            path = [(i, j)]
            while (i, j) in prev:
                i, j = prev[(i, j)]
                path.append((i, j))
            return path[::-1]
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < w and 0 <= nj < h:
                k = nj * w + ni
                if not seen[k] and not g.blocked[k]:
                    seen[k] = 1
                    prev[(ni, nj)] = (i, j)
                    q.append((ni, nj))
    return None


def simplify(path):
    """Cell path -> the corners of it."""
    out = [path[0]]
    for k in range(1, len(path) - 1):
        ax, ay = path[k - 1]
        bx, by = path[k]
        cx, cy = path[k + 1]
        if (bx - ax, by - ay) != (cx - bx, cy - by):
            out.append(path[k])
    out.append(path[-1])
    return out


# ------------------------------------------------------------------ board --

def pour_nets(board):
    """Which nets actually have a filled zone on this board.

    Read off the board, not listed here: the boards do not agree about it --
    the channel half pours -5V and the digital half pours +3V3 -- and a
    hard-coded list silently skips whatever it has not heard of. It did
    exactly that, and reported a board with three stranded supply pads as
    fully connected.
    """
    return {z.GetNetname() for z in board.Zones() if z.GetNetname()}


def stranded(board, path):
    """Pads DRC says are unconnected, by its own reckoning.

    Not by pcbnew's GetConnectedPads/GetConnectedTracks: those know nothing
    about zone connections, so every pad that reaches its net only through the
    pour -- which is most of them -- looks stranded, and on this board 69 of 70
    came back as false positives. kicad-cli's DRC understands zone fills.
    """
    nets = pour_nets(board)
    rpt = os.path.join(tempfile.gettempdir(), "stitch_drc.json")
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json",
                    "-o", rpt, path], capture_output=True, text=True,
                   check=False)
    with open(rpt, encoding="utf-8") as f:
        data = json.load(f)
    by_pos = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            c = pad.GetPosition()
            by_pos[(round(ToMM(c.x), 2), round(ToMM(c.y), 2))] = (
                fp.GetReference(), pad.GetNumber(), pad)
    out, seen = [], set()
    for item in data.get("unconnected_items", []):
        for sub in item.get("items", []):
            desc = sub.get("description", "")
            if "pad" not in desc:
                continue
            net = desc.split("[")[-1].split("]")[0] if "[" in desc else ""
            if net not in nets:
                continue
            key = (round(sub["pos"]["x"], 2), round(sub["pos"]["y"], 2))
            if key in by_pos and key not in seen:
                seen.add(key)
                out.append((net,) + by_pos[key])
    return out


def outline_bbox(board):
    bb = board.GetBoardEdgesBoundingBox()
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
            ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def add_path(board, net, g, cells):
    n = board.FindNet(net)
    pts = [g.mm(i, j) for i, j in cells]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(FromMM(ax), FromMM(ay)))
        t.SetEnd(VECTOR2I(FromMM(bx), FromMM(by)))
        t.SetWidth(FromMM(TRACK_W))
        t.SetLayer(pcbnew.B_Cu)
        t.SetNet(n)
        board.Add(t)
    return len(pts) - 1


def main(path):
    total, failed = 0, []
    for rnd in range(ROUNDS):
        board = pcbnew.LoadBoard(path)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        todo = stranded(board, path)
        if not todo:
            print(f"round {rnd + 1}: every pour pad is connected")
            break
        print(f"round {rnd + 1}: {len(todo)} pad(s) off the pour")
        bbox = outline_bbox(board)
        grids, added, failed = {}, 0, []
        for net, ref, num, pad in todo:
            if net not in grids:
                grids[net] = build_grid(board, net, bbox)
            g = grids[net]
            c = pad.GetPosition()
            cells = route(g, g.cell(ToMM(c.x), ToMM(c.y)))
            if cells is None:
                i, j = g.cell(ToMM(c.x), ToMM(c.y))
                why = ("its own cell is inside another net's clearance"
                       if 0 <= i < g.w and 0 <= j < g.h
                       and g.blocked[j * g.w + i] else "walled in")
                failed.append(f"{ref}.{num}[{net}] ({why})")
                continue
            segs = add_path(board, net, g, simplify(cells))
            length = (len(cells) - 1) * GRID
            print(f"    {ref}.{num:>3} [{net}] {length:5.1f} mm, {segs} segment(s)")
            added += 1
            # the new copper is an obstacle to nothing on its own net, but it
            # IS new goal: later pads may reach the trunk through it
            for i, j in cells:
                g.goal[j * g.w + i] = 1
        total += added
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(path, board)
        if not added:
            break

    print(f"{total} stitch path(s) added on B.Cu")
    if failed:
        print(f"{len(failed)} still off the pour, no legal path: "
              + " ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else "vinyl_adc_analog.kicad_pcb"))
