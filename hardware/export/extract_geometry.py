"""Extract enclosure-relevant geometry from the three Vinyl ADC KiCad boards.

Pure Python 3 (no third-party modules).  Reads each .kicad_pcb, parses the
s-expression tree and writes hardware/export/board_geometry.json with, per board:

  outline   : Edge.Cuts bounding box (mm) and the raw segments/rects
  holes     : every MountingHole footprint (ref, x, y, drill diameter)
  footprints: every footprint with ref, value, lib id, x, y, rot, layer,
              courtyard bbox (mm, absolute) and whether a 3D model is referenced

All coordinates are KiCad board coordinates (mm, +Y down).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KICAD = HERE.parent / "kicad"
BOARDS = {
    "power": KICAD / "power" / "vinyl_adc_power.kicad_pcb",
    "channel_l": KICAD / "channel_l" / "vinyl_adc_channel_l.kicad_pcb",
    "digital": KICAD / "digital" / "vinyl_adc_digital.kicad_pcb",
}


# ---------------------------------------------------------------- s-expr parser
def parse(text: str):
    """Minimal s-expression parser -> nested lists of str/float."""
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == '"':
                    break
                buf.append(text[j])
                j += 1
            tokens.append(('str', "".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            tokens.append(('atom', text[i:j]))
            i = j

    def build(pos):
        out = []
        while pos < len(tokens):
            t = tokens[pos]
            if t == "(":
                sub, pos = build(pos + 1)
                out.append(sub)
            elif t == ")":
                return out, pos + 1
            else:
                kind, val = t
                if kind == 'atom':
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                out.append(val)
                pos += 1
        return out, pos

    tree, _ = build(0)
    return tree[0]


def children(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def child(node, key, default=None):
    cs = children(node, key)
    return cs[0] if cs else default


# ------------------------------------------------------------------ geometry
def rot_pt(x, y, deg):
    r = math.radians(deg)
    # KiCad footprint rotation is CCW in a +Y-down frame; positive rot rotates
    # local +X toward local -Y on screen.  Apply standard 2D rotation on the
    # local coordinates then map: x' = x cos - (-y) sin ... keep it simple by
    # rotating in a Y-up frame.
    yu = -y
    xr = x * math.cos(r) - yu * math.sin(r)
    yr = x * math.sin(r) + yu * math.cos(r)
    return xr, -yr


def footprint_info(fp):
    lib = fp[1]
    at = child(fp, "at")
    x, y = float(at[1]), float(at[2])
    rot = float(at[3]) if len(at) > 3 else 0.0
    layer = child(fp, "layer")[1]
    ref = value = None
    for prop in children(fp, "property"):
        if prop[1] == "Reference":
            ref = prop[2]
        elif prop[1] == "Value":
            value = prop[2]
    models = [m[1] for m in children(fp, "model")]

    # courtyard bbox from F.CrtYd / B.CrtYd graphic lines / rects
    pts = []
    for g in fp:
        if not isinstance(g, list) or not g:
            continue
        if g[0] in ("fp_line", "fp_rect"):
            lay = child(g, "layer")
            if not lay or "CrtYd" not in str(lay[1]):
                continue
            s, e = child(g, "start"), child(g, "end")
            pts += [(float(s[1]), float(s[2])), (float(e[1]), float(e[2]))]
        elif g[0] == "fp_poly":
            lay = child(g, "layer")
            if not lay or "CrtYd" not in str(lay[1]):
                continue
            for p in child(g, "pts"):
                if isinstance(p, list) and p[0] == "xy":
                    pts.append((float(p[1]), float(p[2])))
    if not pts:  # fall back to pads
        for pad in children(fp, "pad"):
            pat = child(pad, "at")
            sz = child(pad, "size")
            px, py = float(pat[1]), float(pat[2])
            hw, hh = float(sz[1]) / 2, float(sz[2]) / 2
            pts += [(px - hw, py - hh), (px + hw, py + hh)]
    abs_pts = [rot_pt(px, py, rot) for px, py in pts]
    abs_pts = [(x + px, y + py) for px, py in abs_pts]
    xs = [p[0] for p in abs_pts] or [x]
    ys = [p[1] for p in abs_pts] or [y]
    bbox = [round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)]

    # pads (for hole diameter on mounting holes / pin positions on headers)
    pads = []
    for pad in children(fp, "pad"):
        pat = child(pad, "at")
        px, py = rot_pt(float(pat[1]), float(pat[2]), rot)
        drill = child(pad, "drill")
        d = float(drill[1]) if drill and isinstance(drill[1], float) else None
        pads.append({"n": str(pad[1]), "x": round(x + px, 3), "y": round(y + py, 3), "drill": d})

    return {
        "ref": ref, "value": value, "lib": lib, "x": x, "y": y, "rot": rot,
        "layer": layer, "bbox": bbox, "models": models, "pads": pads,
    }


def outline_info(pcb):
    segs = []
    xs, ys = [], []
    for g in pcb:
        if not isinstance(g, list) or not g:
            continue
        if g[0] in ("gr_line", "gr_rect"):
            lay = child(g, "layer")
            if not lay or lay[1] != "Edge.Cuts":
                continue
            s, e = child(g, "start"), child(g, "end")
            seg = [float(s[1]), float(s[2]), float(e[1]), float(e[2])]
            segs.append({"type": g[0], "pts": seg})
            xs += [seg[0], seg[2]]
            ys += [seg[1], seg[3]]
        elif g[0] == "gr_arc":
            lay = child(g, "layer")
            if not lay or lay[1] != "Edge.Cuts":
                continue
            for k in ("start", "mid", "end"):
                p = child(g, k)
                xs.append(float(p[1])); ys.append(float(p[2]))
            segs.append({"type": "gr_arc"})
        elif g[0] == "gr_circle":
            lay = child(g, "layer")
            if not lay or lay[1] != "Edge.Cuts":
                continue
            c, e = child(g, "center"), child(g, "end")
            r = math.dist((c[1], c[2]), (e[1], e[2]))
            xs += [c[1] - r, c[1] + r]; ys += [c[2] - r, c[2] + r]
            segs.append({"type": "gr_circle", "center": [c[1], c[2]], "r": r})
    if not xs:
        return None
    return {
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "size": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)],
        "segments": segs,
    }


def main():
    result = {}
    for name, path in BOARDS.items():
        pcb = parse(path.read_text(encoding="utf-8"))
        fps = [footprint_info(fp) for fp in children(pcb, "footprint")]
        holes = [
            {"ref": f["ref"], "x": f["x"], "y": f["y"],
             "drill": next((p["drill"] for p in f["pads"] if p["drill"]), None)}
            for f in fps if "MountingHole" in f["lib"]
        ]
        result[name] = {
            "file": str(path.relative_to(KICAD.parent.parent)),
            "outline": outline_info(pcb),
            "holes": holes,
            "footprints": fps,
            "n_footprints": len(fps),
            "n_without_model": sum(1 for f in fps if not f["models"]),
        }
    out = HERE / "board_geometry.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    # human summary
    for name, b in result.items():
        o = b["outline"]
        print(f"== {name}: outline bbox {o['bbox']} size {o['size']} mm, "
              f"{b['n_footprints']} footprints, {b['n_without_model']} without 3D model")
        for h in b["holes"]:
            print(f"   hole {h['ref']:>4} at ({h['x']:.3f}, {h['y']:.3f}) drill {h['drill']}")
        for f in b["footprints"]:
            if not f["models"] or any(k in f["lib"] for k in ("PinHeader", "Terminal", "Conn", "Jumper")):
                tag = "NO-MODEL " if not f["models"] else ""
                print(f"   {tag}{f['ref']:>5} {f['value']:<22} {f['lib'].split(':')[-1]:<45} "
                      f"at ({f['x']:.2f},{f['y']:.2f}) rot {f['rot']:.0f} bbox {f['bbox']}")
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
