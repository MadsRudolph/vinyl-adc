"""Report per-node bounding boxes (mm) from the kicad-cli GLB exports.

Pure Python: reads the glTF JSON chunk, walks nodes -> meshes -> primitives and
uses the mandatory POSITION accessor min/max.  Node transforms are applied
(translation/rotation/scale or matrix).  KiCad exports in metres; we print mm.
Writes hardware/export/board_heights.json.
"""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_glb(path: Path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF", path
    off = 12
    js = None
    while off < length:
        clen, ctype = struct.unpack_from("<I4s", data, off)
        off += 8
        if ctype == b"JSON":
            js = json.loads(data[off:off + clen])
        off += clen
    return js


def quat_to_mat(q):
    x, y, z, w = q
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def node_matrix(n):
    if "matrix" in n:
        m = n["matrix"]  # column major 4x4
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = n.get("translation", [0, 0, 0])
    r = quat_to_mat(n.get("rotation", [0, 0, 0, 1]))
    s = n.get("scale", [1, 1, 1])
    M = [[r[i][j] * s[j] for j in range(3)] + [t[i]] for i in range(3)]
    M.append([0, 0, 0, 1])
    return M


def matmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def xform(M, p):
    return [sum(M[i][j] * p[j] for j in range(3)) + M[i][3] for i in range(3)]


def walk(js, idx, parent, out, depth=0):
    n = js["nodes"][idx]
    M = matmul(parent, node_matrix(n))
    name = n.get("name", f"node{idx}")
    if "mesh" in n:
        mesh = js["meshes"][n["mesh"]]
        mn = [1e9] * 3
        mx = [-1e9] * 3
        for prim in mesh["primitives"]:
            acc = js["accessors"][prim["attributes"]["POSITION"]]
            lo, hi = acc["min"], acc["max"]
            for cx in (lo[0], hi[0]):
                for cy in (lo[1], hi[1]):
                    for cz in (lo[2], hi[2]):
                        p = xform(M, [cx, cy, cz])
                        for k in range(3):
                            mn[k] = min(mn[k], p[k]); mx[k] = max(mx[k], p[k])
        out.append({"name": name, "min": mn, "max": mx})
    for c in n.get("children", []):
        walk(js, c, M, out, depth + 1)


def main():
    result = {}
    for board in ("power", "channel_l", "digital"):
        path = HERE / f"vinyl-adc-{board}.glb"
        js = read_glb(path)
        scene = js["scenes"][js.get("scene", 0)]
        I = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
        nodes = []
        for root in scene["nodes"]:
            walk(js, root, I, nodes)
        # glTF is +Y up; KiCad exports mm as metres -> scale 1000
        S = 1000.0
        rows = []
        for nd in nodes:
            rows.append({
                "name": nd["name"],
                "x": [round(nd["min"][0] * S, 2), round(nd["max"][0] * S, 2)],
                "y": [round(nd["min"][1] * S, 2), round(nd["max"][1] * S, 2)],
                "z": [round(nd["min"][2] * S, 2), round(nd["max"][2] * S, 2)],
            })
        allmin = [min(r[k][0] for r in rows) for k in ("x", "y", "z")]
        allmax = [max(r[k][1] for r in rows) for k in ("x", "y", "z")]
        result[board] = {"nodes": rows, "bbox_min": allmin, "bbox_max": allmax}
        print(f"== {board}: {len(rows)} mesh nodes, bbox min {allmin} max {allmax} (mm, glTF axes)")
        for r in sorted(rows, key=lambda r: -r["y"][1])[:12]:
            print(f"   {r['name']:<40} x{r['x']} y{r['y']} z{r['z']}")
    (HERE / "board_heights.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    sys.exit(main())
