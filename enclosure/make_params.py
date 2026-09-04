"""Derive the enclosure / stack parameters from the KiCad geometry exports.

Single source of truth for the assembly:  reads
    hardware/export/board_geometry.json   (from extract_geometry.py)
    hardware/export/board_heights.json    (from glb_heights.py)
and writes
    enclosure/vinyl_adc_params.scad       (consumed by vinyl_adc_enclosure.scad)
    enclosure/assembly.json               (consumed by render/build_scene.py)

All units mm.  Enclosure frame:  origin at the outer bottom-left-front corner of
the base, X to the right, Y toward the back, Z up.

    X_enc = X_kicad - 20 + CLR + WALL
    Y_enc = (120 - Y_kicad) + CLR + WALL      (KiCad +Y is down on screen)
    Z_enc = FLOOR + BOSS_H + T_PCB + (tier-1) * TIER_PITCH   (board top surface)
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPORT = HERE.parent / "hardware" / "export"

geo = json.loads((EXPORT / "board_geometry.json").read_text())
hts = json.loads((EXPORT / "board_heights.json").read_text())

# ------------------------------------------------------------------ constants
CLR = 0.5          # board-to-wall clearance, all sides (spec)
WALL = 3.0         # wall thickness (spec)
FLOOR = 3.0        # base floor thickness
LID_T = 3.0        # lid plate thickness
LID_LIP_H = 4.0    # lid locating lip, drops inside the wall
LID_LIP_T = 2.0
LID_LIP_CLR = 0.25 # per-side clearance lip-to-wall
T_PCB = 1.6        # FR4 thickness (KiCad default, matches GLB: body -1.6..0)
BOSS_H = 6.0       # floor boss height above the floor (M3 heat-set insert)
BOSS_D = 8.0
INSERT_D = 4.0     # hole for an M3 x 5.7 heat-set insert
INSERT_DEPTH = 7.0
STANDOFF = 18.0    # M3 male-female brass standoff between tiers and to lid
CORNER_R = 3.0     # outer vertical edge radius
PIN_PROTRUSION = 1.7  # solder-side lead length, from GLB (bbox min y = -1.7)
IDC_SOCKET_H = 11.5   # 2x8 IDC socket seated on the header, top above board
RIBBON_FOLD = 4.0     # ribbon exits the socket top and folds sideways

TIER_PITCH = STANDOFF + T_PCB  # 19.6

# ------------------------------------------------------------- board checks
for name, b in geo.items():
    bb = b["outline"]["bbox"]
    assert bb == [20.0, 20.0, 120.0, 120.0], (name, bb)
BOARD = 100.0
KX0, KY0, KY1 = 20.0, 20.0, 120.0
INNER = BOARD + 2 * CLR      # 101
OUTER = INNER + 2 * WALL     # 107


def ex(kx):  # KiCad x -> enclosure X
    return round(kx - KX0 + CLR + WALL, 3)


def ey(ky):  # KiCad y -> enclosure Y (flipped)
    return round((KY1 - ky) + CLR + WALL, 3)


TIERS = [  # bottom to top
    {"tier": 1, "board": "power", "label": "Power & reference"},
    {"tier": 2, "board": "channel_l", "label": "Channel R modulator (channel_l artwork, jumper R)"},
    {"tier": 3, "board": "channel_l", "label": "Channel L modulator"},
    {"tier": 4, "board": "digital", "label": "Clock, interleave & Pi interface"},
]
for t in TIERS:
    t["z_top"] = round(FLOOR + BOSS_H + T_PCB + (t["tier"] - 1) * TIER_PITCH, 3)
    t["z_bottom"] = round(t["z_top"] - T_PCB, 3)
    h = hts[t["board"]]
    t["max_component_height"] = round(h["bbox_max"][1], 2)  # glTF y is up

# tallest thing on any tier = IDC socket + ribbon fold on the bus header
stack_need = max(IDC_SOCKET_H + RIBBON_FOLD,
                 max(t["max_component_height"] for t in TIERS)) + PIN_PROTRUSION
assert STANDOFF >= stack_need, f"standoff {STANDOFF} < needed {stack_need}"

Z_LID_UNDER = round(TIERS[-1]["z_top"] + STANDOFF, 3)    # wall top / lid underside
Z_OUTER_TOP = round(Z_LID_UNDER + LID_T, 3)

# mounting holes (identical on all boards - assert it)
holes_k = sorted((h["x"], h["y"]) for h in geo["power"]["holes"])
for name, b in geo.items():
    assert sorted((h["x"], h["y"]) for h in b["holes"]) == holes_k, name
    assert all(h["drill"] == 3.2 for h in b["holes"]), name
HOLES = [[ex(x), ey(y)] for x, y in holes_k]


def fp(board, ref):
    return next(f for f in geo[board]["footprints"] if f["ref"] == ref)


# ------------------------------------------------------------------ cutouts
cutouts = []

# LINE IN screw terminals J20 on both channel tiers -> +X (right) wall.
j20 = fp("channel_l", "J20")
bx0, by0, bx1, by1 = j20["bbox"]  # courtyard, KiCad frame
assert bx1 > 119.0, "J20 must sit at the +X board edge for a wall window"
TB_MARGIN = 0.75
TB_H = 11.0  # window height above board top (bornier body ~10.6 mm)
for t in TIERS:
    if t["board"] != "channel_l":
        continue
    cutouts.append({
        "kind": "window", "wall": "+X", "ref": "J20", "tier": t["tier"],
        "label": f"LINE IN {'R' if t['tier'] == 2 else 'L'}",
        "kicad": {"ref_at": [j20["x"], j20["y"]], "rot": j20["rot"], "bbox": j20["bbox"]},
        "y0": round(ey(by1) - TB_MARGIN, 3), "y1": round(ey(by0) + TB_MARGIN, 3),
        "z0": round(t["z_top"] + 0.3, 3), "z1": round(t["z_top"] + 0.3 + TB_H, 3),
    })

# Gain trimmer RV20 on both channel tiers -> -Y (front) wall, screwdriver hole.
rv = fp("channel_l", "RV20")
assert rv["bbox"][3] > 118.0, "RV20 must sit at the front board edge"
TRIM_D = 5.0
TRIM_Z = 5.0  # screw axis height above board top (Bourns 3296X/Y side-adjust)
for t in TIERS:
    if t["board"] != "channel_l":
        continue
    cutouts.append({
        "kind": "hole", "wall": "-Y", "ref": "RV20", "tier": t["tier"],
        "label": f"GAIN {'R' if t['tier'] == 2 else 'L'}",
        "kicad": {"ref_at": [rv["x"], rv["y"]], "rot": rv["rot"], "bbox": rv["bbox"]},
        "x": ex(rv["x"]), "z": round(t["z_top"] + TRIM_Z, 3), "d": TRIM_D,
    })

# Pi GPIO header J2 on the digital tier -> -Y (front) wall, open notch.
j2 = fp("digital", "J2")
assert j2["bbox"][3] > 117.0, "J2 must sit at the front board edge"
NOTCH_MARGIN = 1.5
top = next(t for t in TIERS if t["board"] == "digital")
cutouts.append({
    "kind": "notch", "wall": "-Y", "ref": "J2", "tier": top["tier"],
    "label": "TO PI GPIO (8-way ribbon)",
    "kicad": {"ref_at": [j2["x"], j2["y"]], "rot": j2["rot"], "bbox": j2["bbox"]},
    "x0": round(ex(j2["bbox"][0]) - NOTCH_MARGIN, 3),
    "x1": round(ex(j2["bbox"][2]) + NOTCH_MARGIN, 3),
    "z0": round(top["z_top"] + 3.0, 3), "z1": Z_LID_UNDER,
})

# ------------------------------------------------------------------ outputs
params = {
    "CLR": CLR, "WALL": WALL, "FLOOR": FLOOR, "LID_T": LID_T,
    "LID_LIP_H": LID_LIP_H, "LID_LIP_T": LID_LIP_T, "LID_LIP_CLR": LID_LIP_CLR,
    "T_PCB": T_PCB, "BOSS_H": BOSS_H, "BOSS_D": BOSS_D, "INSERT_D": INSERT_D,
    "INSERT_DEPTH": INSERT_DEPTH, "STANDOFF": STANDOFF, "CORNER_R": CORNER_R,
    "TIER_PITCH": TIER_PITCH, "BOARD": BOARD, "INNER": INNER, "OUTER": OUTER,
    "Z_LID_UNDER": Z_LID_UNDER, "Z_OUTER_TOP": Z_OUTER_TOP,
    "HOLES": HOLES,
    "TIER_Z_TOP": [t["z_top"] for t in TIERS],
}
lines = ["// GENERATED by make_params.py from the KiCad exports - do not edit by hand.",
         "// All dimensions in mm.  See make_params.py for the derivation."]
for k, v in params.items():
    lines.append(f"{k} = {json.dumps(v)};")
# cutout lists as flat vectors for OpenSCAD 2021
lines.append("// windows: [y0, y1, z0, z1]  on the +X wall")
lines.append("WINDOWS_PX = " + json.dumps([[c["y0"], c["y1"], c["z0"], c["z1"]]
                                           for c in cutouts if c["kind"] == "window"]) + ";")
lines.append("// holes: [x, z, d]  on the -Y wall")
lines.append("HOLES_MY = " + json.dumps([[c["x"], c["z"], c["d"]]
                                         for c in cutouts if c["kind"] == "hole"]) + ";")
lines.append("// notches: [x0, x1, z0, z1]  on the -Y wall, open to the top edge")
lines.append("NOTCHES_MY = " + json.dumps([[c["x0"], c["x1"], c["z0"], c["z1"]]
                                           for c in cutouts if c["kind"] == "notch"]) + ";")
(HERE / "vinyl_adc_params.scad").write_text("\n".join(lines) + "\n", encoding="utf-8")

assembly = {
    "units": "mm",
    "frame": "enclosure: origin outer bottom-left-front corner, X right, Y back, Z up",
    "kicad_to_enclosure": {"X": "kx - 20 + 0.5 + 3", "Y": "(120 - ky) + 0.5 + 3"},
    "params": params, "tiers": TIERS, "cutouts": cutouts,
    "board_glb": {"power": "hardware/export/vinyl-adc-power.glb",
                  "channel_l": "hardware/export/vinyl-adc-channel_l.glb",
                  "digital": "hardware/export/vinyl-adc-digital.glb"},
    "outer_size": [OUTER, OUTER, Z_OUTER_TOP],
    "stack_clearance_needed": stack_need,
}
(HERE / "assembly.json").write_text(json.dumps(assembly, indent=1), encoding="utf-8")

print(f"outer {OUTER} x {OUTER} x {Z_OUTER_TOP} mm, inner {INNER}, tier pitch {TIER_PITCH}, "
      f"standoff {STANDOFF} (needs >= {stack_need:.1f})")
for t in TIERS:
    print(f"  tier {t['tier']} {t['board']:<10} board top Z={t['z_top']:<6} "
          f"max part {t['max_component_height']} mm")
print("holes (enclosure XY):", HOLES)
for c in cutouts:
    print("  cutout", {k: v for k, v in c.items() if k != "kicad"})
