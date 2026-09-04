"""Verify the enclosure cutouts against the connector coordinates in the
.kicad_pcb files AND against the exported base STL.  Pure Python.

Two independent checks per cutout:

  1. Coordinates: re-read the footprint from the board file (own parser, not
     assembly.json), map its courtyard into the enclosure frame and require
     the cutout to contain it (with the design margins).
  2. Geometry: cast rays through the base STL at sample points inside the
     cutout on the wall's mid-plane and require them to be OUTSIDE the solid
     (i.e. the wall really is open there), and at points just beyond the
     cutout edge to be INSIDE (the wall is still there).

    python enclosure/check_cutouts.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "hardware" / "export"))
from extract_geometry import parse, children, footprint_info  # noqa: E402

ASM = json.loads((HERE / "assembly.json").read_text())
P = ASM["params"]
CLR, WALL = P["CLR"], P["WALL"]
KX0, KY1 = 20.0, 120.0


def ex(kx):
    return kx - KX0 + CLR + WALL


def ey(ky):
    return (KY1 - ky) + CLR + WALL


BOARDS = {
    "channel_l": ROOT / "hardware/kicad/channel_l/vinyl_adc_channel_l.kicad_pcb",
    "digital": ROOT / "hardware/kicad/digital/vinyl_adc_digital.kicad_pcb",
}
FPS = {}
for name, path in BOARDS.items():
    pcb = parse(path.read_text(encoding="utf-8"))
    FPS[name] = {f["ref"]: f for f in (footprint_info(fp) for fp in children(pcb, "footprint"))}


# ----------------------------------------------------------------- STL ray test
sys.path.insert(0, str(HERE))
from check_stl import read_stl  # noqa: E402  (ASCII or binary STL)

TRIS = read_stl(HERE / "vinyl-adc-base.stl")


def inside(p, tris=TRIS):
    """Point-in-solid via the generalised winding number (sum of signed solid
    angles, Van Oosterom & Strackee).  Robust to rays grazing edges, which a
    crossing count is not."""
    import math
    px, py, pz = p
    total = 0.0
    for a, b, c in tris:
        ax, ay, az = a[0] - px, a[1] - py, a[2] - pz
        bx, by, bz = b[0] - px, b[1] - py, b[2] - pz
        cx, cy, cz = c[0] - px, c[1] - py, c[2] - pz
        la = math.sqrt(ax * ax + ay * ay + az * az)
        lb = math.sqrt(bx * bx + by * by + bz * bz)
        lc = math.sqrt(cx * cx + cy * cy + cz * cz)
        det = (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx))
        den = (la * lb * lc + (ax * bx + ay * by + az * bz) * lc
               + (ax * cx + ay * cy + az * cz) * lb + (bx * cx + by * cy + bz * cz) * la)
        total += 2.0 * math.atan2(det, den)
    return abs(total) > 2.0 * math.pi  # ~4*pi inside, ~0 outside


def wall_point(c, u, v):
    """Point on the mid-plane of the wall for cutout c, at in-wall coords (u, v)."""
    if c["wall"] == "+X":
        return (P["OUTER"] - WALL / 2, u, v)
    if c["wall"] == "-Y":
        return (u, WALL / 2, v)
    raise ValueError(c["wall"])


# ----------------------------------------------------------------- checks
ok = True
print("Enclosure frame: X = kx - 16.5, Y = 123.5 - ky (mm).  Tier board tops:",
      [t["z_top"] for t in ASM["tiers"]])
for c in ASM["cutouts"]:
    board = "digital" if c["ref"] == "J2" else "channel_l"
    f = FPS[board][c["ref"]]
    tier = next(t for t in ASM["tiers"] if t["tier"] == c["tier"])
    bx0, by0, bx1, by1 = f["bbox"]
    # courtyard in enclosure coords
    ex0, ex1 = ex(bx0), ex(bx1)
    ey0, ey1 = ey(by1), ey(by0)
    print(f"\n{c['label']}: {c['ref']} on tier {c['tier']} ({board}) "
          f"KiCad at ({f['x']:.2f}, {f['y']:.2f}) rot {f['rot']:.0f}, courtyard x[{bx0},{bx1}] y[{by0},{by1}]")
    print(f"   -> enclosure X[{ex0:.3f},{ex1:.3f}] Y[{ey0:.3f},{ey1:.3f}], board top Z={tier['z_top']}")
    if c["kind"] == "window":
        good = c["y0"] <= ey0 and c["y1"] >= ey1 and c["z0"] >= tier["z_top"] and c["z0"] < tier["z_top"] + 1
        print(f"   window Y[{c['y0']},{c['y1']}] Z[{c['z0']},{c['z1']}]  covers courtyard Y: {good}")
        samples_open = [(u, v) for u in (c["y0"] + 0.5, (c["y0"] + c["y1"]) / 2, c["y1"] - 0.5)
                        for v in (c["z0"] + 0.5, (c["z0"] + c["z1"]) / 2, c["z1"] - 0.5)]
        samples_wall = [((c["y0"] + c["y1"]) / 2, c["z0"] - 1.0), ((c["y0"] + c["y1"]) / 2, c["z1"] + 1.0),
                        (c["y0"] - 1.0, (c["z0"] + c["z1"]) / 2), (c["y1"] + 1.0, (c["z0"] + c["z1"]) / 2)]
    elif c["kind"] == "hole":
        cx = ex(f["x"])
        good = abs(cx - c["x"]) < 1e-6 and tier["z_top"] < c["z"] < tier["z_top"] + 11
        print(f"   hole at X={c['x']} Z={c['z']} d={c['d']}  centred on RV20 x: {good}")
        r = c["d"] / 2
        samples_open = [(c["x"], c["z"]), (c["x"] + r * 0.6, c["z"]), (c["x"] - r * 0.6, c["z"]),
                        (c["x"], c["z"] + r * 0.6), (c["x"], c["z"] - r * 0.6)]
        samples_wall = [(c["x"] + r + 1.0, c["z"]), (c["x"] - r - 1.0, c["z"]),
                        (c["x"], c["z"] + r + 1.0), (c["x"], c["z"] - r - 1.0)]
    else:  # notch
        good = c["x0"] <= ex0 and c["x1"] >= ex1 and c["z0"] > tier["z_top"] and c["z1"] >= P["Z_LID_UNDER"]
        print(f"   notch X[{c['x0']},{c['x1']}] Z[{c['z0']},{c['z1']}]  covers courtyard X and reaches wall top: {good}")
        samples_open = [(u, v) for u in (c["x0"] + 0.5, (c["x0"] + c["x1"]) / 2, c["x1"] - 0.5)
                        for v in (c["z0"] + 0.5, (c["z0"] + c["z1"]) / 2, c["z1"] - 0.5)]
        samples_wall = [((c["x0"] + c["x1"]) / 2, c["z0"] - 1.0),
                        (c["x0"] - 1.0, (c["z0"] + c["z1"]) / 2), (c["x1"] + 1.0, (c["z0"] + c["z1"]) / 2)]
    ok &= good
    opens = [not inside(wall_point(c, u, v)) for u, v in samples_open]
    walls = [inside(wall_point(c, u, v)) for u, v in samples_wall]
    print(f"   STL: {sum(opens)}/{len(opens)} sample points inside the cutout are open, "
          f"{sum(walls)}/{len(walls)} points just outside it are solid wall")
    ok &= all(opens) and all(walls)

# mounting bosses: STL must be solid at the boss ring and open at the insert hole
print("\nFloor bosses / heat-set insert holes:")
for (hx, hy) in P["HOLES"]:
    z = P["FLOOR"] + P["BOSS_H"] - 1.0
    ring = inside((hx + 3.0, hy, z))
    hole = not inside((hx, hy, z))
    print(f"   boss at ({hx}, {hy}): ring solid {ring}, insert hole open {hole}")
    ok &= ring and hole

print("\nRESULT:", "ALL CUTOUTS VERIFIED" if ok else "MISMATCH FOUND")
sys.exit(0 if ok else 1)
