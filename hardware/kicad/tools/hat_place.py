#!/usr/bin/env python3
r"""Netlist-driven placement for the rev D (through-hole) and rev E (SMD) HATs.

Rev D's first layout packed passives into rows by type, first-fit, inside
bands: tidy from across the room and wrong up close, because a resistor in
a row sits wherever the row had space, not next to the pin it serves, and
every such distance is a trace crossing the board.  This placer does the
opposite: the board file names a handful of anchors (connectors, the LED
row, the Pi socket, hints for the ICs) and a region for everything else,
and every free part is put where its NETS want it.

  1. greedy: parts go down in order of how strongly they connect to what is
     already placed, each at the free spot nearest the centroid of the pads
     it connects to (a decoupling cap: the supply pin it decouples);
  2. anneal: moves, rotations and same-footprint swaps, minimising
     weighted half-perimeter wire length plus the decoupling distances,
     never allowing two courtyards (plus a gap) to overlap or a part to
     leave its region;
  3. tidy: parts nudged onto their neighbours' rows and columns where that
     costs (almost) nothing, so the board reads in lines.

Plane nets (GND, +5V, +5VA) carry no wire-length weight -- they are one via
away everywhere -- which is exactly why decoupling caps need their own term:
without it nothing pulls a 100 n toward the chip it serves.

TWINS: channel R is placed as a rigid translated copy of channel L.  The
two channels are the same circuit; the same copper makes them the same
circuit on the board too (matching, and one layout to review, not two).

Pure-python geometry after one pcbnew pass per footprint and rotation, so a
few hundred thousand moves take tens of seconds.
"""
import math
import os
import random
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROTS = (0, 90, 180, 270)
PLANE_NETS = ("GND", "+5V", "+5VA")


def _bbox_mm(fp):
    """Courtyard bbox if the footprint has one, else pads + graphics."""
    try:
        fp.BuildCourtyardCaches()
    except Exception:
        pass
    boxes = []
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        try:
            poly = fp.GetCourtyard(layer)
            if poly.OutlineCount():
                boxes.append(poly.BBox())
        except Exception:
            pass
    if boxes:
        x0 = min(ToMM(b.GetLeft()) for b in boxes)
        y0 = min(ToMM(b.GetTop()) for b in boxes)
        x1 = max(ToMM(b.GetRight()) for b in boxes)
        y1 = max(ToMM(b.GetBottom()) for b in boxes)
        return x0, y0, x1, y1
    bb = fp.GetBoundingBox(False, False)
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
            ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


class Part:
    def __init__(self, ref, fp):
        self.ref, self.fp = ref, fp
        self.geo = {}                 # rot -> (bbox rel, [(num, dx, dy, net)])
        o = fp.GetOrientationDegrees()
        pos = fp.GetPosition()
        for r in ROTS:
            fp.SetOrientationDegrees(r)
            fp.SetPosition(VECTOR2I(0, 0))
            pads = [(p.GetNumber(), ToMM(p.GetPosition().x),
                     ToMM(p.GetPosition().y), p.GetNetname())
                    for p in fp.Pads()]
            self.geo[r] = (_bbox_mm(fp), pads)
        fp.SetOrientationDegrees(o)
        fp.SetPosition(pos)
        self.x = self.y = 0.0
        self.rot = 0
        self.placed = False
        self.fixed = False
        self.region = None
        self.rots = ROTS
        self.twin = None              # (slave Part, dx, dy): moves with this
        self.master = None
        self.tht = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
                       for p in fp.Pads())
        self.halo = 0.0               # extra clearance: a routing channel

    def box(self, x=None, y=None, rot=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        (x0, y0, x1, y1), _ = self.geo[self.rot if rot is None else rot]
        return x + x0, y + y0, x + x1, y + y1

    def pads(self, x=None, y=None, rot=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        return [(n, x + dx, y + dy, net)
                for n, dx, dy, net in self.geo[self.rot if rot is None else rot][1]]

    def size(self, rot=0):
        (x0, y0, x1, y1), _ = self.geo[rot]
        return x1 - x0, y1 - y0


class Placer:
    CELL = 4.0

    def __init__(self, fps, W, H, gap=0.3, margin=0.6, snap=0.25,
                 weights=None, seed=1):
        self.W, self.H = W, H
        self.gap, self.margin, self.snap = gap, margin, snap
        self.parts = {r: Part(r, fp) for r, fp in fps.items()}
        self.obst = []                        # absolute boxes nothing may touch
        self.weights = dict(weights or {})
        for n in PLANE_NETS:
            self.weights.setdefault(n, 0.0)
        self.decap = {}                       # cap ref -> (host ref, pad, net)
        self.dec_w = 4.0
        self.pulls = {}                       # ref -> (x, y, weight)
        self.plane_at = None                  # (x, y) -> net of the In2 plane
        self.plane_nets = ("+5V", "+5VA")
        self.rng = random.Random(seed)
        self.grid = {}
        # nets -> [(ref, padnum)]
        self.nets = {}
        for p in self.parts.values():
            for n, _dx, _dy, net in p.geo[0][1]:
                if net:
                    self.nets.setdefault(net, []).append((p.ref, n))
        self.part_nets = {r: sorted({net for _n, _x, _y, net in p.geo[0][1]
                                     if net and self.w(net) > 0})
                          for r, p in self.parts.items()}

    # ---------------------------------------------------------------- setup
    def w(self, net):
        if net in self.weights:
            return self.weights[net]
        return 1.0 if len(self.nets.get(net, ())) > 1 else 0.0

    def obstacle(self, box):
        self.obst.append(box)

    def fix(self, ref, x, y, rot=0):
        p = self.parts[ref]
        p.x, p.y, p.rot = x, y, rot
        p.placed = p.fixed = True
        self._grid_add(p)

    def hint(self, ref, x, y, rot=0, rots=None):
        """Initial position for a part the annealer may still move: its
        courtyard CENTRE at (x, y), turned `rot`."""
        p = self.parts[ref]
        (x0, y0, x1, y1), _ = p.geo[rot]
        p.hint = (x - (x0 + x1) / 2, y - (y0 + y1) / 2, rot)
        if rots:
            p.rots = rots

    def region(self, refs, rect, rots=None):
        for r in refs:
            p = self.parts[r]
            if p.fixed:
                continue
            p.region = rect
            if rots:
                p.rots = rots

    def twin(self, master, slave, dx, dy):
        m, s = self.parts[master], self.parts[slave]
        m.twin = (s, dx, dy)
        s.master = m

    def decouple(self, cap, host):
        """Pull `cap`'s supply pad to the pin of `host` on the same net."""
        c, h = self.parts[cap], self.parts[host]
        for _n, _x, _y, net in c.geo[0][1]:
            if net and net != "GND":
                for hn, _hx, _hy, hnet in h.geo[0][1]:
                    if hnet == net:
                        self.decap[cap] = (host, hn, net)
                        # a crowded block can leave no room by the pin: the
                        # cap may use its host's block as well as its own
                        # (the plane term keeps it on the right side of the
                        # split)
                        c.region = self._union(c.region, h.region)
                        return
        raise SystemExit(f"{cap} shares no supply with {host}")

    @staticmethod
    def _union(a, b):
        if a is None or b is None:
            return a or b
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]),
                max(a[3], b[3]))

    def pull(self, ref, x, y, weight=1.0):
        """A soft spring to a point (a part that belongs near an edge)."""
        self.pulls[ref] = (x, y, weight)

    # ---------------------------------------------------------------- grid
    def _cells(self, box):
        x0, y0, x1, y1 = box
        c = self.CELL
        for i in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for j in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                yield (i, j)

    def _grid_add(self, p):
        for cell in self._cells(p.box()):
            self.grid.setdefault(cell, set()).add(p.ref)

    def _grid_del(self, p):
        for cell in self._cells(p.box()):
            s = self.grid.get(cell)
            if s:
                s.discard(p.ref)

    # ---------------------------------------------------------------- rules
    def _gap(self, a, b):
        return self.gap * (2.0 if (a.tht and b.tht) else 1.0) + a.halo + b.halo

    def halo(self, refs, mm):
        """Keep `mm` of extra space round these parts: a channel for the
        traces that fan out of an IC's pins, which wire length alone would
        close up."""
        for r in refs:
            self.parts[r].halo = mm

    def ok(self, p, x, y, rot, ignore=()):
        """Can p sit at (x, y, rot) -- and its twin at the offset?"""
        todo = [(p, x, y, rot)]
        if p.twin:
            s, dx, dy = p.twin
            todo.append((s, x + dx, y + dy, rot))
        skip = set(ignore) | {q.ref for q, *_ in todo}
        for q, qx, qy, qr in todo:
            x0, y0, x1, y1 = q.box(qx, qy, qr)
            m = self.margin
            if x0 < m or y0 < m or x1 > self.W - m or y1 > self.H - m:
                return False
            reg = q.region if q.master is None else None
            if reg:
                rx0, ry0, rx1, ry1 = reg
                if x0 < rx0 or y0 < ry0 or x1 > rx1 or y1 > ry1:
                    return False
            for ox0, oy0, ox1, oy1 in self.obst:
                if x0 < ox1 and ox0 < x1 and y0 < oy1 and oy0 < y1:
                    return False
            seen = set()
            for cell in self._cells((x0, y0, x1, y1)):
                for r in self.grid.get(cell, ()):
                    if r in skip or r in seen:
                        continue
                    seen.add(r)
                    o = self.parts[r]
                    g = self._gap(q, o)
                    a0, b0, a1, b1 = o.box()
                    if x0 < a1 + g and a0 < x1 + g and y0 < b1 + g and b0 < y1 + g:
                        return False
            # the pair must not collide with itself either
            for q2, qx2, qy2, qr2 in todo:
                if q2 is q:
                    continue
                a0, b0, a1, b1 = q2.box(qx2, qy2, qr2)
                if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
                    return False
        return True

    def check_fixed(self):
        """Anchors against each other, the obstacles and the outline."""
        out = []
        fixed = [p for p in self.parts.values() if p.fixed]
        for i, p in enumerate(fixed):
            x0, y0, x1, y1 = p.box()
            if x0 < 0 or y0 < 0 or x1 > self.W or y1 > self.H:
                out.append(f"{p.ref} leaves the board: "
                           f"({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f})")
            for b in self.obst:
                if x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1:
                    out.append(f"{p.ref} ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f})"
                               f" hits obstacle {tuple(round(v, 1) for v in b)}")
            for q in fixed[i + 1:]:
                a0, b0, a1, b1 = q.box()
                if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
                    out.append(f"{p.ref} overlaps {q.ref}")
        return out

    # ---------------------------------------------------------------- cost
    def _padpos(self, ref, num):
        p = self.parts[ref]
        for n, x, y, _net in p.pads():
            if n == num:
                return x, y
        raise KeyError((ref, num))

    def net_cost(self, net):
        wt = self.w(net)
        if wt <= 0:
            return 0.0
        xs, ys = [], []
        for ref, num in self.nets[net]:
            p = self.parts[ref]
            if not p.placed:
                continue
            x, y = self._padpos(ref, num)
            xs.append(x)
            ys.append(y)
        if len(xs) < 2:
            return 0.0
        return wt * ((max(xs) - min(xs)) + (max(ys) - min(ys)))

    def dec_cost(self, cap):
        host, hn, net = self.decap[cap]
        c, h = self.parts[cap], self.parts[host]
        if not (c.placed and h.placed):
            return 0.0
        cx, cy = next((x, y) for _n, x, y, nt in c.pads() if nt == net)
        hx, hy = self._padpos(host, hn)
        return self.dec_w * math.hypot(cx - hx, cy - hy)

    def plane_cost(self, ref):
        """1000 per supply pad that would land in the other net's plane."""
        if self.plane_at is None:
            return 0.0
        p = self.parts[ref]
        if not p.placed:
            return 0.0
        return 1000.0 * sum(1 for _n, x, y, net in p.pads()
                            if net in self.plane_nets and self.plane_at(x, y) != net)

    def pull_cost(self, ref):
        x, y, wt = self.pulls[ref]
        p = self.parts[ref]
        if not p.placed:
            return 0.0
        return wt * (abs(p.x - x) + abs(p.y - y))

    def local_cost(self, refs):
        nets, caps, pulls = set(), set(), set()
        for r in refs:
            nets.update(self.part_nets[r])
            if r in self.decap:
                caps.add(r)
            if r in self.pulls:
                pulls.add(r)
        for cap, (host, _hn, _net) in self.decap.items():
            if host in refs:
                caps.add(cap)
        return (sum(self.net_cost(n) for n in nets)
                + sum(self.dec_cost(c) for c in caps)
                + sum(self.pull_cost(r) for r in pulls)
                + sum(self.plane_cost(r) for r in refs))

    def total(self):
        return (sum(self.net_cost(n) for n in self.nets)
                + sum(self.dec_cost(c) for c in self.decap)
                + sum(self.pull_cost(r) for r in self.pulls)
                + sum(self.plane_cost(r) for r in self.parts))

    # ---------------------------------------------------------------- moves
    def _set(self, p, x, y, rot):
        self._grid_del(p)
        p.x, p.y, p.rot = x, y, rot
        self._grid_add(p)
        if p.twin:
            s, dx, dy = p.twin
            self._grid_del(s)
            s.x, s.y, s.rot = x + dx, y + dy, rot
            self._grid_add(s)

    def _group(self, p):
        g = [p.ref]
        if p.twin:
            g.append(p.twin[0].ref)
        return g

    def _q(self, v):
        return round(v / self.snap) * self.snap

    def _target(self, p):
        """Centroid of the placed pads p connects to (weighted)."""
        sx = sy = sw = 0.0
        for net in self.part_nets[p.ref]:
            wt = self.w(net)
            for ref, num in self.nets[net]:
                q = self.parts[ref]
                if ref == p.ref or not q.placed or q is (p.twin[0] if p.twin else None):
                    continue
                x, y = self._padpos(ref, num)
                sx, sy, sw = sx + wt * x, sy + wt * y, sw + wt
        if p.ref in self.decap:
            host, hn, _net = self.decap[p.ref]
            if self.parts[host].placed:
                x, y = self._padpos(host, hn)
                sx, sy, sw = sx + 6 * x, sy + 6 * y, sw + 6
        if hasattr(p, "hint"):
            hx, hy, _ = p.hint
            sx, sy, sw = sx + 3 * hx, sy + 3 * hy, sw + 3
        if sw == 0:
            if p.region:
                x0, y0, x1, y1 = p.region
                return (x0 + x1) / 2, (y0 + y1) / 2
            return self.W / 2, self.H / 2
        return sx / sw, sy / sw

    def greedy(self):
        todo = [p for p in self.parts.values()
                if not p.placed and p.master is None]
        # hinted parts (the ICs) first, in the file's order, then the rest by
        # how much they already connect to
        hinted = [p for p in todo if hasattr(p, "hint")]
        for p in hinted:
            x, y, r = p.hint
            self._drop(p, x, y, [r] + [q for q in p.rots if q != r])
        rest = [p for p in todo if not hasattr(p, "hint")]
        # decoupling caps straight after their ICs, so they claim the spot
        # by the supply pin before anything else can; then big parts before
        # small ones, or the small ones fill the holes the big ones needed
        dec = [p for p in rest if p.ref in self.decap]
        rest = [p for p in rest if p.ref not in self.decap]
        big = [p for p in rest if p.size()[0] * p.size()[1] > 40]
        for group in (dec, big, [p for p in rest if p not in big]):
            self._greedy(group)

    def _greedy(self, rest):
        rest = list(rest)
        while rest:
            def score(p):
                s = 0.0
                for net in self.part_nets[p.ref]:
                    s += self.w(net) * sum(1 for ref, _ in self.nets[net]
                                           if self.parts[ref].placed)
                if p.ref in self.decap and self.parts[self.decap[p.ref][0]].placed:
                    s += 5
                return s
            rest.sort(key=score, reverse=True)
            p = rest.pop(0)
            tx, ty = self._target(p)
            self._drop(p, tx, ty, p.rots)

    def _drop(self, p, tx, ty, rots):
        """Nearest free spot to (tx, ty), best cost within the first ring
        that has one."""
        step = self.snap * 2
        best = None
        for ring in range(0, 400):
            cands = []
            if ring == 0:
                pts = [(0, 0)]
            else:
                pts = []
                for k in range(-ring, ring + 1):
                    pts += [(k, -ring), (k, ring)]
                for k in range(-ring + 1, ring):
                    pts += [(-ring, k), (ring, k)]
            for i, j in pts:
                x, y = self._q(tx + i * step), self._q(ty + j * step)
                for r in rots:
                    if self.ok(p, x, y, r):
                        cands.append((x, y, r))
            if cands:
                for x, y, r in cands:
                    p.x, p.y, p.rot, p.placed = x, y, r, True
                    if p.twin:
                        s, dx, dy = p.twin
                        s.x, s.y, s.rot, s.placed = x + dx, y + dy, r, True
                    c = self.local_cost(self._group(p))
                    if best is None or c < best[0]:
                        best = (c, x, y, r)
                p.placed = False
                if p.twin:
                    p.twin[0].placed = False
                if ring > 2 or best[0] == 0:
                    break
        if best is None:
            self.plot("/tmp/claude-1000/hat_place_fail.png")
            raise SystemExit(f"no room for {p.ref} (region {p.region}); "
                             "see /tmp/claude-1000/hat_place_fail.png")
        _c, x, y, r = best
        p.placed = True
        p.x, p.y, p.rot = x, y, r
        self._grid_add(p)
        if p.twin:
            s, dx, dy = p.twin
            s.placed = True
            s.x, s.y, s.rot = x + dx, y + dy, r
            self._grid_add(s)

    def anneal(self, iters=200000, t0=None, t1=0.02, ic_rate=0.25, log=True):
        movable = [p for p in self.parts.values()
                   if not p.fixed and p.master is None]
        if not movable:
            return
        swaps = {}
        for p in movable:
            key = (p.fp.GetFPIDAsString(), p.region)
            swaps.setdefault(key, []).append(p)
        cur = self.total()
        if t0 is None:
            t0 = max(1.0, cur / len(movable) * 0.3)
        big = [p for p in movable if hasattr(p, "hint")]
        small = [p for p in movable if not hasattr(p, "hint")]
        acc = 0
        for it in range(iters):
            frac = it / iters
            T = t0 * (t1 / t0) ** frac
            reach = max(self.snap * 2, 12.0 * (1 - frac) ** 2)
            pool = big if (big and self.rng.random() < ic_rate * len(big) /
                           max(1, len(movable)) * 4) else small or big
            p = self.rng.choice(pool)
            mv = self.rng.random()
            if mv < 0.12:                                  # swap
                sib = swaps[(p.fp.GetFPIDAsString(), p.region)]
                if len(sib) < 2:
                    continue
                q = self.rng.choice(sib)
                if q is p:
                    continue
                refs = self._group(p) + self._group(q)
                before = self.local_cost(refs)
                pa, qa = (p.x, p.y, p.rot), (q.x, q.y, q.rot)
                self._set(p, *qa)
                self._set(q, *pa)
                okp = self.ok(p, p.x, p.y, p.rot) and self.ok(q, q.x, q.y, q.rot)
                d = self.local_cost(refs) - before if okp else None
                if d is None or (d > 0 and self.rng.random() >= math.exp(-d / T)):
                    self._set(p, *pa)
                    self._set(q, *qa)
                else:
                    cur += d
                    acc += 1
                continue
            if mv < 0.30:                                  # rotate
                r = self.rng.choice(p.rots)
                if r == p.rot:
                    continue
                x, y = p.x, p.y
            elif mv < 0.45:                                # home: near its pins
                r = self.rng.choice(p.rots)
                if p.ref in self.decap:
                    host, hn, _net = self.decap[p.ref]
                    tx, ty = self._padpos(host, hn)
                    rad = 5.0
                else:
                    tx, ty = self._target(p)
                    rad = max(2.0, reach)
                x = self._q(tx + self.rng.uniform(-rad, rad))
                y = self._q(ty + self.rng.uniform(-rad, rad))
            else:                                          # shift
                r = p.rot
                x = self._q(p.x + self.rng.uniform(-reach, reach))
                y = self._q(p.y + self.rng.uniform(-reach, reach))
            refs = self._group(p)
            old = (p.x, p.y, p.rot)
            before = self.local_cost(refs)
            self._grid_del(p)
            if p.twin:
                self._grid_del(p.twin[0])
            fine = self.ok(p, x, y, r)
            self._grid_add(p)
            if p.twin:
                self._grid_add(p.twin[0])
            if not fine:
                continue
            self._set(p, x, y, r)
            d = self.local_cost(refs) - before
            if d > 0 and self.rng.random() >= math.exp(-d / T):
                self._set(p, *old)
            else:
                cur += d
                acc += 1
            if log and it % (iters // 10 or 1) == 0:
                print(f"    anneal {it:7d}  T {T:7.3f}  cost {cur:9.1f}  "
                      f"accepted {acc}", flush=True)
        if log:
            print(f"    anneal done: cost {self.total():.1f}")

    def tidy(self, tol=1.2, slack=0.3):
        """Snap parts onto a neighbour's row or column when it is free and
        costs at most `slack` of wire length."""
        movable = [p for p in self.parts.values()
                   if not p.fixed and p.master is None and not hasattr(p, "hint")]
        moved = 0
        for p in movable:
            best = None
            for q in self.parts.values():
                if q is p or not q.placed:
                    continue
                for axis in ("x", "y"):
                    dv = (q.y - p.y) if axis == "y" else (q.x - p.x)
                    if 0 < abs(dv) <= tol:
                        nx = p.x + (dv if axis == "x" else 0)
                        ny = p.y + (dv if axis == "y" else 0)
                        if best is None or abs(dv) < best[0]:
                            best = (abs(dv), nx, ny)
            if not best:
                continue
            _d, nx, ny = best
            refs = self._group(p)
            before = self.local_cost(refs)
            self._grid_del(p)
            if p.twin:
                self._grid_del(p.twin[0])
            fine = self.ok(p, nx, ny, p.rot)
            self._grid_add(p)
            if p.twin:
                self._grid_add(p.twin[0])
            if not fine:
                continue
            old = (p.x, p.y, p.rot)
            self._set(p, nx, ny, p.rot)
            if self.local_cost(refs) - before > slack:
                self._set(p, *old)
            else:
                moved += 1
        return moved

    def apply(self):
        for p in self.parts.values():
            if not p.placed:
                raise SystemExit(f"{p.ref} was never placed")
            p.fp.SetOrientationDegrees(p.rot)
            p.fp.SetPosition(VECTOR2I(FromMM(p.x), FromMM(p.y)))

    def report(self):
        per = {}
        for n in self.nets:
            c = self.net_cost(n)
            if c:
                per[n] = c
        worst = sorted(per.items(), key=lambda kv: -kv[1])[:8]
        dec = sorted(((self.dec_cost(c) / self.dec_w, c) for c in self.decap),
                     reverse=True)[:5]
        print(f"    wire {sum(per.values()):.0f} mm (weighted HPWL); longest: "
              + ", ".join(f"{n} {c:.0f}" for n, c in worst))
        print("    farthest decoupling: "
              + ", ".join(f"{c} {d:.1f} mm" for d, c in dec))

    def plot(self, path):
        """Courtyards, regions and fixed parts as a PNG, for looking at."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        fig, ax = plt.subplots(figsize=(self.W / 8, self.H / 8), dpi=110)
        ax.add_patch(Rectangle((0, 0), self.W, self.H, fill=False, lw=1))
        regs = {p.region for p in self.parts.values() if p.region}
        for x0, y0, x1, y1 in regs:
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                                   ls="--", ec="0.6", lw=0.6))
        for x0, y0, x1, y1 in self.obst:
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="0.85"))
        for p in self.parts.values():
            if not p.placed:
                continue
            x0, y0, x1, y1 = p.box()
            col = ("tab:red" if p.fixed else "tab:blue" if hasattr(p, "hint")
                   else "tab:green")
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                                   ec=col, lw=0.7))
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, p.ref, fontsize=3.2,
                    ha="center", va="center")
        ax.set_xlim(-1, self.W + 1)
        ax.set_ylim(self.H + 1, -1)
        ax.set_aspect("equal")
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
