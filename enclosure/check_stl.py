"""Manifold / watertight check for binary or ASCII STL files.  Pure Python.

A closed 2-manifold triangle mesh has every edge shared by exactly two
triangles, with opposite winding.  Reports: triangle count, unique vertices,
bounding box (mm), edges used once (open) or more than twice (non-manifold),
and the signed volume (positive = consistently outward-facing normals).

    python check_stl.py vinyl-adc-base.stl vinyl-adc-lid.stl
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path


def read_stl(path: Path):
    data = path.read_bytes()
    tris = []
    if data[:5] == b"solid" and b"facet" in data[:400]:
        # ASCII
        verts = []
        for line in data.decode("ascii", "replace").splitlines():
            t = line.strip().split()
            if t and t[0] == "vertex":
                verts.append(tuple(float(v) for v in t[1:4]))
        tris = [tuple(verts[i:i + 3]) for i in range(0, len(verts), 3)]
    else:
        n = struct.unpack_from("<I", data, 80)[0]
        off = 84
        for _ in range(n):
            f = struct.unpack_from("<12fH", data, off)
            off += 50
            tris.append(((f[3], f[4], f[5]), (f[6], f[7], f[8]), (f[9], f[10], f[11])))
    return tris


def check(path: Path):
    tris = read_stl(path)
    key = lambda v: tuple(round(c, 4) for c in v)  # weld within 0.1 um
    edges = Counter()
    verts = set()
    vol = 0.0
    xs, ys, zs = [], [], []
    for a, b, c in tris:
        ka, kb, kc = key(a), key(b), key(c)
        verts.update((ka, kb, kc))
        for p, q in ((ka, kb), (kb, kc), (kc, ka)):
            edges[(p, q)] += 1
        # signed volume of tetrahedron with origin
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        for v in (a, b, c):
            xs.append(v[0]); ys.append(v[1]); zs.append(v[2])
    open_edges = 0
    bad = 0
    for (p, q), n in edges.items():
        m = edges.get((q, p), 0)
        if n != 1 or m != 1:
            if m == 0:
                open_edges += 1
            else:
                bad += 1
    manifold = open_edges == 0 and bad == 0
    print(f"{path.name}: {len(tris)} triangles, {len(verts)} vertices, "
          f"bbox x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(ys):.2f}] z[{min(zs):.2f},{max(zs):.2f}] mm, "
          f"volume {vol / 1000:.2f} cm3, open edges {open_edges}, non-manifold edges {bad} -> "
          f"{'MANIFOLD OK' if manifold else 'NOT MANIFOLD'}")
    return manifold


if __name__ == "__main__":
    ok = all(check(Path(p)) for p in sys.argv[1:])
    sys.exit(0 if ok else 1)
