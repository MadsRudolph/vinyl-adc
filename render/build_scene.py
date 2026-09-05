"""Build the Vinyl ADC product assembly in Blender and render it.

Run headless (Blender 4.4 tested):

    & "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" -b -P render\\build_scene.py -- --samples 128

What it does
  1. reads enclosure/assembly.json (tier heights, cutouts - derived from KiCad)
  2. imports the kicad-cli GLB of each board (channel_l twice), the OpenSCAD
     base and lid STLs, and builds brass standoffs, lid screws, the 16-way
     bus ribbon, the Pi ribbon and the placeholder bodies listed in DECISIONS.md
  3. assigns materials (matte PLA enclosure, brass, steel, PVC ribbon),
     neutral three-light studio + ground plane
  4. renders four 1920x1080 PNGs into render/renders/:
        hero.png, front_panel.png, exploded.png, line_in_side.png
  5. saves render/vinyl-adc-assembly.blend (assembled state) and exports
     hardware/export/vinyl-adc-assembly.glb

Scene units: metres (1 BU = 1 m); every mm figure from assembly.json is
multiplied by 0.001 so lights and camera behave physically.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
ASM = json.loads((ROOT / "enclosure" / "assembly.json").read_text())
P = ASM["params"]
OUT = ROOT / "render" / "renders"
OUT.mkdir(parents=True, exist_ok=True)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SAMPLES = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 128
ENGINE = argv[argv.index("--engine") + 1] if "--engine" in argv else "CYCLES"
ONLY = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
NO_RENDER = "--no-render" in argv


def mm(v):
    return v * 0.001


# ------------------------------------------------------------ scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.unit_settings.length_unit = "MILLIMETERS"

COL = {}


def collection(name):
    if name not in COL:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
        COL[name] = c
    return COL[name]


def link(obj, colname):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    collection(colname).objects.link(obj)
    return obj


# ------------------------------------------------------------ materials
def principled(name, color, rough=0.5, metal=0.0, spec=0.5, coat=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        m.blend_method = "BLEND"
    return m


MAT_PLA = principled("PLA_matte_charcoal", (0.028, 0.029, 0.032), rough=0.72, spec=0.35)
MAT_PLA_LID = principled("PLA_matte_charcoal_lid", (0.028, 0.029, 0.032), rough=0.72, spec=0.35)
MAT_BRASS = principled("Brass", (0.83, 0.62, 0.30), rough=0.32, metal=1.0)
MAT_STEEL = principled("Steel_black_oxide", (0.10, 0.10, 0.11), rough=0.35, metal=1.0)
MAT_RIBBON = principled("Ribbon_grey_PVC", (0.42, 0.43, 0.45), rough=0.55, spec=0.4)
MAT_RIBBON_DARK = principled("Ribbon_dark_PVC", (0.12, 0.12, 0.13), rough=0.55, spec=0.4)
MAT_IDC = principled("IDC_socket_black", (0.03, 0.03, 0.03), rough=0.5)
MAT_TB = principled("Terminal_block_green", (0.05, 0.32, 0.16), rough=0.45)
MAT_WIRE = principled("Wire_link_insulation", (0.75, 0.12, 0.10), rough=0.5)
MAT_GROUND = principled("Studio_ground", (0.80, 0.80, 0.80), rough=0.55, spec=0.3)
MAT_DUPONT = principled("Dupont_housing", (0.04, 0.04, 0.045), rough=0.55)


# ------------------------------------------------------------ primitives
def box(name, size, center, mat, col):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=tuple(mm(c) for c in center))
    o = bpy.context.active_object
    o.name = name
    o.scale = tuple(mm(s) for s in size)
    o.data.materials.append(mat)
    return link(o, col)


def cyl(name, d, h, center_bottom, mat, col, verts=48, axis="Z"):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=mm(d / 2), depth=mm(h),
                                        location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    cx, cy, cz = center_bottom
    if axis == "Z":
        o.location = (mm(cx), mm(cy), mm(cz + h / 2))
    elif axis == "Y":
        o.rotation_euler = (math.radians(90), 0, 0)
        o.location = (mm(cx), mm(cy + h / 2), mm(cz))
    return link(o, col)


def smooth(o, angle=30):
    """Smooth shading with sharp edges above `angle` - mesh-data API, works headless."""
    if o.type == "MESH" and o.data is not None:
        me = o.data
        me.shade_smooth()
        try:
            me.set_sharp_from_angle(angle=math.radians(angle))
        except Exception:
            pass


# ------------------------------------------------------------ imports
def import_stl(path: Path, name, mat, col):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=str(path), global_scale=0.001)
    new = [o for o in bpy.data.objects if o not in before]
    o = new[0]
    o.name = name
    o.data.materials.clear()
    o.data.materials.append(mat)
    smooth(o, 35)
    return link(o, col)


KX0, KY1 = 20.0, 120.0
OFF_X = -KX0 + P["CLR"] + P["WALL"]          # -16.5
OFF_Y = KY1 + P["CLR"] + P["WALL"]           # 123.5 (Blender Y = -kicad y after glTF import)


def import_board(glb: Path, tier):
    """Import a kicad-cli GLB under an Empty placed at the tier height.

    glTF (metres, Y-up) -> Blender Z-up:  X = kx, Y = -ky, Z = up.
    Enclosure frame:  X_enc = kx - 16.5,  Y_enc = 123.5 - ky,  Z = z_top.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(f"Tier{tier['tier']}_{tier['board']}", None)
    root.empty_display_type = "PLAIN_AXES"
    link(root, "Boards")
    for o in new:
        if o.parent is None or o.parent not in new:
            o.parent = root
        link(o, "Boards")
        if o.type == "MESH":
            o.name = f"T{tier['tier']}_{o.name}"
            smooth(o, 30)
    root.location = (mm(OFF_X), mm(OFF_Y), mm(tier["z_top"]))
    return root


def board_glb_root_children(root):
    return [c for c in root.children_recursive if c.type == "MESH"]


# ------------------------------------------------------------ placeholders
def placeholder_terminal_block(tier, fp_ref="J20"):
    """TerminalBlock_bornier-2_P5.08mm has no 3D model.  Body from the
    footprint F.Fab outline: local x -2.46..7.54, y -3.75..3.75, rot 90 at
    KiCad (115.80, 100.75) -> body centre KiCad (115.80, 98.21), 7.5 (x) x 10 (y),
    height 10.6 mm (typical bornier).  Two M2.5 screw heads on top."""
    z = tier["z_top"]
    cx, cy = 115.80 + OFF_X, OFF_Y - 98.21
    body = box(f"T{tier['tier']}_J20_placeholder_body", (7.5, 10.0, 10.6), (cx, cy, z + 5.3), MAT_TB, "Placeholders")
    for k, dy in enumerate((-2.54, 2.54)):
        cyl(f"T{tier['tier']}_J20_placeholder_screw{k+1}", 3.0, 0.6, (cx - 1.0, cy + dy, z + 10.6), MAT_STEEL, "Placeholders", verts=24)
    # wire entry holes on the +X face (cosmetic recesses)
    for k, dy in enumerate((-2.54, 2.54)):
        h = cyl(f"T{tier['tier']}_J20_placeholder_entry{k+1}", 2.6, 1.0, (cx + 3.75 - 0.5, cy + dy, z + 4.5), MAT_STEEL, "Placeholders", verts=24)
        h.rotation_euler = (0, math.radians(90), 0)
        h.location = (mm(cx + 3.75 - 0.4), mm(cy + dy), mm(z + 4.5))
    return body


def placeholder_wire_links(geo_board, tier):
    """WireLink_TH pads come in A/B pairs: one insulated jumper wire on the
    component side between them.  Modelled as a 0.8 mm wire 1.2 mm above the board."""
    fps = [f for f in geo_board["footprints"] if "WireLink" in f["lib"]]
    pairs = {}
    for f in fps:
        key = f["ref"][:-1]
        pairs.setdefault(key, {})[f["ref"][-1]] = f
    z = tier["z_top"] + 1.2
    for key, ab in pairs.items():
        if "A" not in ab or "B" not in ab:
            continue
        a, b = ab["A"], ab["B"]
        ax, ay = a["x"] + OFF_X, OFF_Y - a["y"]
        bx, by = b["x"] + OFF_X, OFF_Y - b["y"]
        L = math.hypot(bx - ax, by - ay)
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=mm(0.4), depth=mm(L), location=(mm((ax + bx) / 2), mm((ay + by) / 2), mm(z)))
        o = bpy.context.active_object
        o.name = f"T{tier['tier']}_{key}_wirelink_placeholder"
        o.rotation_euler = (0, math.radians(90), math.atan2(by - ay, bx - ax))
        o.data.materials.append(MAT_WIRE)
        link(o, "Placeholders")
        for (x, y) in ((ax, ay), (bx, by)):  # vertical legs
            cyl(f"T{tier['tier']}_{key}_leg", 0.8, 1.2, (x, y, tier["z_top"]), MAT_WIRE, "Placeholders", verts=12)


def idc_socket_and_ribbon(tiers):
    """16-way IDC sockets on the 2x8 bus header (KiCad (78.89,30.0) rot -90 on
    every board, long axis along X) daisy-chained by one ribbon at the back."""
    cx, cy = 69.985 + OFF_X, OFF_Y - 30.0   # header courtyard centre x=(59.34+80.66)/2
    for t in tiers:
        z = t["z_top"]
        box(f"T{t['tier']}_IDC_socket", (24.3, 8.6, 9.0), (cx, cy, z + 2.5 + 4.5), MAT_IDC, "Cables")
        # strain-relief tab where the ribbon leaves the socket top
        box(f"T{t['tier']}_IDC_ribbon_tab", (20.3, 1.0, 5.0), (cx, cy + 4.3 + 0.5, z + 11.5 - 2.5), MAT_RIBBON, "Cables")
    z0 = tiers[0]["z_top"] + 11.5 - 2.5
    z1 = tiers[-1]["z_top"] + 11.5
    box("Bus_ribbon_16way", (20.3, 1.0, z1 - z0), (cx, cy + 4.3 + 0.5, (z0 + z1) / 2), MAT_RIBBON, "Cables")


def pi_ribbon(tier):
    """8-way Dupont ribbon on J2 (KiCad (60.22,115.60) rot 90 -> pins along X,
    courtyard x 58.45..79.77).  Housings 14 mm tall, ribbon folds forward and
    leaves through the front-wall notch."""
    z = tier["z_top"]
    cx, cy = (58.45 + 79.77) / 2 + OFF_X, OFF_Y - 115.60
    box("Pi_dupont_housings", (20.5, 2.6, 14.0), (cx, cy, z + 7.0), MAT_DUPONT, "Cables")
    box("Pi_ribbon_vertical", (20.3, 1.2, 6.0), (cx, cy - 1.9, z + 14.0 + 3.0), MAT_RIBBON_DARK, "Cables")
    box("Pi_ribbon_out", (20.3, 36.0, 1.2), (cx, cy - 18.0, z + 20.0 - 0.6), MAT_RIBBON_DARK, "Cables")


# ------------------------------------------------------------ build
GEO = json.loads((ROOT / "hardware" / "export" / "board_geometry.json").read_text())
tiers = ASM["tiers"]
tier_roots = []
for t in tiers:
    root = import_board(ROOT / ASM["board_glb"][t["board"]], t)
    tier_roots.append(root)
    if t["board"] == "channel_l":
        placeholder_terminal_block(t)
    placeholder_wire_links(GEO[t["board"]], t)

base = import_stl(ROOT / "enclosure" / "vinyl-adc-base.stl", "Enclosure_base", MAT_PLA, "Enclosure")
lid = import_stl(ROOT / "enclosure" / "vinyl-adc-lid.stl", "Enclosure_lid", MAT_PLA_LID, "Enclosure")

# standoffs: M3 x 18 male-female brass hex, one per hole per tier (16 total)
for t in tiers:
    for k, (hx, hy) in enumerate(P["HOLES"]):
        s = cyl(f"Standoff_T{t['tier']}_{k+1}", 5.5 / math.cos(math.pi / 6), P["STANDOFF"], (hx, hy, t["z_top"]), MAT_BRASS, "Hardware", verts=6)
        # male thread of the standoff below passes through the board: show the
        # thread stub between board bottom and the female top below
        cyl(f"Standoff_T{t['tier']}_{k+1}_thread", 2.9, P["T_PCB"] + 0.2, (hx, hy, t["z_bottom"] - 0.1), MAT_BRASS, "Hardware", verts=16)
# lid screws: M3 socket head in the counterbores
for k, (hx, hy) in enumerate(P["HOLES"]):
    cyl(f"Lid_screw_{k+1}_head", 5.4, 2.0, (hx, hy, P["Z_OUTER_TOP"] - 2.0), MAT_STEEL, "Hardware", verts=24)
    cyl(f"Lid_screw_{k+1}_socket", 2.5, 0.6, (hx, hy, P["Z_OUTER_TOP"] - 0.6 + 0.01), MAT_STEEL, "Hardware", verts=6)

idc_socket_and_ribbon(tiers)
pi_ribbon(tiers[-1])

# group everything that moves with a tier under its root (for the exploded view)
for o in list(collection("Placeholders").objects) + list(collection("Cables").objects) + list(collection("Hardware").objects):
    if o.name.startswith("T") and o.name[1].isdigit() and o.name[2] == "_":
        tnum = int(o.name[1])
    elif o.name.startswith("Standoff_T"):
        tnum = int(o.name[len("Standoff_T")])
    else:
        continue
    root = tier_roots[tnum - 1]
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()

# ------------------------------------------------------------ studio
bpy.ops.mesh.primitive_plane_add(size=12.0, location=(mm(P["OUTER"] / 2), mm(P["OUTER"] / 2), -0.0002))
ground = bpy.context.active_object
ground.name = "Studio_ground"
ground.data.materials.append(MAT_GROUND)
link(ground, "Studio")

world = bpy.data.worlds.new("Studio_world")
scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]            # what the lights/bounces see: dim, cool
bg.inputs[0].default_value = (0.72, 0.74, 0.78, 1.0)
bg.inputs[1].default_value = 0.12
bg_cam = nt.nodes.new("ShaderNodeBackground")   # what the camera sees: seamless light-grey cove
bg_cam.inputs[0].default_value = (0.86, 0.86, 0.87, 1.0)
bg_cam.inputs[1].default_value = 0.85
lp = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixShader")
out = nt.nodes["World Output"]
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
nt.links.new(bg.outputs[0], mix.inputs[1])
nt.links.new(bg_cam.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs["Surface"])


def area_light(name, loc, target, size, energy, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = color
    ld.shape = "RECTANGLE"
    ld.size_y = size * 0.6
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    d = (Vector(target) - Vector(loc)).normalized()
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    link(o, "Studio")
    return o


C = Vector((mm(P["OUTER"] / 2), mm(P["OUTER"] / 2), mm(P["Z_OUTER_TOP"] / 2)))
# Blender light "watts" are not physical at this scale: these values were
# tuned so an 80 % grey ground reads mid-grey under AgX at exposure 0.
area_light("Key", (C.x + 0.35, C.y - 0.45, C.z + 0.55), C, 0.6, 9.0, (1.0, 0.97, 0.93))
area_light("Fill", (C.x - 0.6, C.y - 0.25, C.z + 0.25), C, 0.9, 3.5, (0.93, 0.96, 1.0))
area_light("Rim", (C.x - 0.15, C.y + 0.7, C.z + 0.6), C, 0.5, 8.0)
area_light("Top", (C.x, C.y, C.z + 0.9), C, 1.2, 2.5)

# ------------------------------------------------------------ cameras
SENSOR = 36.0
RES = (1920, 1080)


def scene_bbox(exclude=("Studio", "Cables")):
    bpy.context.view_layer.update()  # refresh matrix_world after moving parents
    lo = Vector((1e9,) * 3)
    hi = Vector((-1e9,) * 3)
    for o in bpy.data.objects:
        if o.type != "MESH" or any(c.name in exclude for c in o.users_collection):
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def make_camera(name, direction, lens=50, fit=0.85, target=None, fstop=None, include_cables=False):
    """Place a camera looking along -direction at the scene bbox centre, at
    the exact distance where every bbox corner projects inside `fit` of the
    frame (frustum fit, not a bounding sphere)."""
    lo, hi = scene_bbox(exclude=("Studio",) if include_cables else ("Studio", "Cables"))
    ctr = target or (lo + hi) / 2
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = SENSOR
    cam.sensor_fit = "HORIZONTAL"
    cam.clip_start = 0.005
    cam.clip_end = 50
    tan_h = (SENSOR / 2) / lens * fit
    tan_v = (SENSOR * RES[1] / RES[0] / 2) / lens * fit
    d = Vector(direction).normalized()
    q = d.to_track_quat("Z", "Y")
    right, up = q @ Vector((1, 0, 0)), q @ Vector((0, 1, 0))
    dist = 0.0
    for cx in (lo.x, hi.x):
        for cy in (lo.y, hi.y):
            for cz in (lo.z, hi.z):
                rel = Vector((cx, cy, cz)) - ctr
                along = rel.dot(d)
                dist = max(dist, along + abs(rel.dot(right)) / tan_h, along + abs(rel.dot(up)) / tan_v)
    o = bpy.data.objects.new(name, cam)
    o.location = ctr + d * dist
    o.rotation_euler = q.to_euler()
    if fstop:
        cam.dof.use_dof = True
        cam.dof.focus_distance = dist
        cam.dof.aperture_fstop = fstop
    link(o, "Cameras")
    return o


# ------------------------------------------------------------ render setup
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = 0.0
scene.render.engine = ENGINE
if ENGINE == "CYCLES":
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    # try to use a GPU if one is available
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = backend
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == backend]
                if devs:
                    for d in prefs.devices:
                        d.use = d.type in (backend, "CPU")
                    scene.cycles.device = "GPU"
                    print("Cycles GPU backend:", backend, [d.name for d in devs])
                    break
            except Exception:
                continue
    except Exception as e:
        print("GPU setup skipped:", e)
else:
    scene.eevee.taa_render_samples = max(64, SAMPLES)


def render(cam, name):
    if ONLY and name not in ONLY:
        return
    scene.camera = cam
    scene.render.filepath = str(OUT / f"{name}.png")
    t0 = time.time()
    if not NO_RENDER:
        bpy.ops.render.render(write_still=True)
    print(f"rendered {name} in {time.time() - t0:.1f}s -> {scene.render.filepath}")


# assembled shots ---------------------------------------------------------
cam_hero = make_camera("Cam_hero", (1.0, -1.15, 0.72), lens=50, fit=0.90, fstop=8)
cam_front = make_camera("Cam_front_panel", (0.55, -1.0, 0.22), lens=60, fit=0.82, include_cables=True)
cam_side = make_camera("Cam_line_in_side", (1.0, -0.35, 0.25), lens=60, fit=0.82)
render(cam_hero, "hero")
render(cam_front, "front_panel")
render(cam_side, "line_in_side")

# exploded ----------------------------------------------------------------
EXPLODE_FIRST = 62.0   # tier 1 lifts this much (its parts clear the wall top)
EXPLODE_TIER = 34.0    # extra lift per tier above it
LID_LIFT = 45.0        # lid lift above the top standoffs
tier_lift = [EXPLODE_FIRST + EXPLODE_TIER * i for i in range(len(tier_roots))]
lid_lift = tier_lift[-1] + LID_LIFT
for root, dz in zip(tier_roots, tier_lift):
    root.location.z += mm(dz)
lid.location.z += mm(lid_lift)
for o in bpy.data.objects:
    if o.name.startswith("Lid_screw"):
        o.location.z += mm(lid_lift)
    if o.name.startswith("Bus_ribbon") or o.name.startswith("Pi_"):
        o.hide_render = True
cam_expl = make_camera("Cam_exploded", (1.0, -0.95, 0.9), lens=50, fit=0.88, fstop=11)
render(cam_expl, "exploded")

# restore & save ------------------------------------------------------------
for root, dz in zip(tier_roots, tier_lift):
    root.location.z -= mm(dz)
lid.location.z -= mm(lid_lift)
for o in bpy.data.objects:
    if o.name.startswith("Lid_screw"):
        o.location.z -= mm(lid_lift)
    if o.name.startswith("Bus_ribbon") or o.name.startswith("Pi_"):
        o.hide_render = False
scene.camera = cam_hero

blend = ROOT / "render" / "vinyl-adc-assembly.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
print("saved", blend)

def export_glb(path, collections):
    for o in bpy.data.objects:
        o.select_set(o.type in ("MESH", "EMPTY") and any(c.name in collections for c in o.users_collection))
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_apply=True)
    print("exported", path)


# full product (boards + placeholders + cables + hardware + enclosure)
export_glb(ROOT / "hardware" / "export" / "vinyl-adc-assembly.glb",
           ("Boards", "Placeholders", "Cables", "Hardware", "Enclosure"))
# the four-tier board stack alone, with its standoffs and placeholders (deliverable 1)
export_glb(ROOT / "hardware" / "export" / "vinyl-adc-board.glb",
           ("Boards", "Placeholders", "Hardware"))
