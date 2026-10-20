"""Showcase renders of the rev D HAT (Cycles, headless).

    blender -b --factory-startup --python hardware/kicad/rev_d/render/render_rev_d.py -- [--shot NAME] [--preview]

Shots: hero, top, detail (stills, straight into media/showcase/rev-d/) and
orbit, explode (72-frame seamless loops into build/frames/<clip>/, encoded by
encode_rev_d.py). No --shot renders all five. --preview renders stills at a
quarter of the samples and half size, and clips as frames 1 and 37 only.
Needs build/board.glb and build/pi4.glb from export_model.sh. Each shot's
scene is saved as build/<shot>.blend for inspection.
"""
import bpy, sys, math, json, argparse, hashlib
from pathlib import Path
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILD = HERE / 'build'
MEDIA = ROOT / 'media/showcase/rev-d'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
VSHOTS = {'v_fly': 150, 'v_orbit': 120, 'v_explode': 120, 'v_led': 120}  # vertical 1080x1920 @ 30 fps, for the short
ap.add_argument('--shot', choices=['hero', 'top', 'detail', 'orbit', 'explode', *VSHOTS], action='append')
ap.add_argument('--frames', help='first:last, for v_* shots (default all)')
ap.add_argument('--preview', action='store_true')
args = ap.parse_args(argv)
SHOTS = args.shot or ['hero', 'top', 'detail', 'orbit', 'explode']

MM = 0.001
# Board outline in KiCad page coordinates (mm): x 51.06..191.06, y 21.5..157.5.
BOARD_X0, BOARD_Y0, BOARD_W, BOARD_H = 51.06, 21.5, 140.0, 136.0
CENTER = Vector(((BOARD_X0 + BOARD_W / 2) * MM, -(BOARD_Y0 + BOARD_H / 2) * MM, 0))
PI_DROP = -11.0  # Pi PCB top below the HAT's copper side: 8.5 mm socket + 2.5 mm header body

# Status LEDs: colour from the footprint Value field, lit as on a running board.
LED_COLOUR = {'RED': (1.0, 0.04, 0.02), 'GREEN': (0.10, 1.0, 0.12), 'YELLOW': (1.0, 0.62, 0.02)}
LEDS = {'D6': 'RED', 'D7': 'RED', 'D5': 'GREEN', 'D4': 'YELLOW', 'D3': 'GREEN',
        'D8': 'RED', 'D9': 'YELLOW', 'D10': 'GREEN'}


# ---------------------------------------------------------------- materials
def principled(name, base, metallic=0.0, rough=0.5, coat=0.0, coat_rough=0.05,
               spec=0.5, alpha=1.0, transmission=0.0, emission=None, strength=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Alpha'].default_value = alpha
    b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['IOR'].default_value = ior
    if emission:
        b.inputs['Emission Color'].default_value = (*emission, 1)
        b.inputs['Emission Strength'].default_value = strength
    return m


def add_noise_bump(m, scale, strength, distance):
    """Fine surface relief (HASL ripple, mask texture)."""
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = 4
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    nt.links.new(n.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def board_materials():
    mats = {}
    # PCBWay green, white legend. The order notes leave the colour open, so the
    # fab's default green is used.
    mats['mask'] = add_noise_bump(principled('soldermask', (0.008, 0.115, 0.032), rough=0.24,
                                             coat=0.5, coat_rough=0.06), 900, 0.05, 0.002)
    mats['silk'] = principled('silkscreen', (0.85, 0.86, 0.84), rough=0.65, spec=0.3)
    # HASL lead-free: bright tin, satin, slightly uneven.
    mats['hasl'] = add_noise_bump(principled('hasl', (0.80, 0.80, 0.79), metallic=1, rough=0.22),
                                  2500, 0.25, 0.003)
    # Copper under the mask (tracks, tented vias): KiCad exports the mask as a
    # flat sheet, so the copper is lifted 30 um through it and shaded as mask
    # over copper -- the lighter, slightly raised traces of a real board.
    mats['copper'] = add_noise_bump(principled('mask_over_copper', (0.030, 0.245, 0.055), rough=0.22,
                                               coat=0.5, coat_rough=0.06), 900, 0.05, 0.002)
    # Laminate: pale on the routed edge, dark under the mask so tracks read
    # through it lighter, as on a real board.
    fr4 = principled('fr4', (0.55, 0.50, 0.30), rough=0.7)
    nt = fr4.node_tree
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ab = nt.nodes.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = (0.55, 0.50, 0.30, 1)
    mix.inputs['B'].default_value = (0.05, 0.06, 0.02, 1)
    nt.links.new(geo.outputs['Normal'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], ab.inputs[0])
    nt.links.new(ab.outputs[0], mix.inputs['Factor'])
    nt.links.new(mix.outputs['Result'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    mats['fr4'] = fr4
    return mats


# Component materials, keyed by the colour KiCad's library models carry.
def component_material(m):
    b = m.node_tree.nodes.get('Principled BSDF')
    if b is None:
        return
    c = tuple(b.inputs['Base Color'].default_value)[:3]
    def near(t, tol=0.02):
        return all(abs(a - x) < tol for a, x in zip(c, t))
    def set_(base, metallic, rough, coat=0.0, spec=0.5, transmission=0.0):
        b.inputs['Base Color'].default_value = (*base, 1)
        b.inputs['Metallic'].default_value = metallic
        b.inputs['Roughness'].default_value = rough
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = 0.1
        b.inputs['Specular IOR Level'].default_value = spec
        b.inputs['Transmission Weight'].default_value = transmission
    if near((0.019, 0.018, 0.018)):            # black epoxy / plastic
        set_((0.012, 0.012, 0.013), 0, 0.42, coat=0.15)
    elif near((0.645, 0.638, 0.572)):          # tinned leads
        set_((0.78, 0.78, 0.76), 1, 0.25)
    elif near((0.619, 0.152, 0.019)):          # ceramic disc caps, dipped
        set_((0.62, 0.30, 0.05), 0, 0.38, coat=0.4)
    elif near((0.754, 0.464, 0.207)):          # axial resistors: blue metal film
        set_((0.16, 0.36, 0.62), 0, 0.33, coat=0.5)
    elif near((0.448, 0.010, 0.004)):          # DO-35 glass (LEDs replaced per part)
        set_((0.75, 0.10, 0.02), 0, 0.08, coat=0.0, transmission=0.6)
    elif near((0.017, 0.134, 0.487)):          # electrolytic sleeve
        set_((0.02, 0.07, 0.25), 0, 0.28, coat=0.7)
    elif near((0.435, 0.398, 0.316)):          # electrolytic can top
        set_((0.75, 0.75, 0.74), 1, 0.35)
    elif near((0.061, 0.061, 0.061)):          # MKT box, choke former
        set_((0.04, 0.04, 0.045), 0, 0.45, coat=0.2)
    elif near((0.709, 0.504, 0.210)):          # gold pin plating
        set_((1.0, 0.76, 0.38), 1, 0.18)
    elif near((0.778, 0.770, 0.626)):          # DO-41 band
        set_((0.75, 0.75, 0.72), 0, 0.5)
    elif near((0.165, 0.165, 0.165)):          # crystal can
        set_((0.82, 0.82, 0.82), 1, 0.15)
    elif near((0.133, 0.061, 0.000)):          # crystal base
        set_((0.05, 0.04, 0.03), 0, 0.5)
    elif near((0.453, 0.059, 0.008)):          # choke ferrite / enamel
        set_((0.35, 0.08, 0.02), 0.3, 0.3, coat=0.5)
    elif near((0.095, 0.420, 0.167)):          # terminal block body
        set_((0.03, 0.18, 0.55), 0, 0.4)
    elif near((0.0, 0.356, 0.519)):            # 1N4148 band
        set_((0.02, 0.02, 0.02), 0, 0.4)
    else:                                       # anything else: tame KiCad's metallic=1 / rough=1
        b.inputs['Metallic'].default_value = 0
        b.inputs['Roughness'].default_value = 0.45


def led_material(colour_name):
    col = LED_COLOUR[colour_name]
    tint = col
    m = principled('led_' + colour_name.lower(), tint, rough=0.05, transmission=0.5,
                   emission=col, strength=1.0, ior=1.5, coat=0.5, coat_rough=0.02)
    return m


# ---------------------------------------------------------------- scene
def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def build_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    hat = bpy.data.objects.new('HAT', None); sc.collection.objects.link(hat)
    pi = bpy.data.objects.new('PI', None); sc.collection.objects.link(pi)

    objs = import_glb(BUILD / 'board.glb')
    for o in objs:
        if o.parent is None:
            o.parent = hat
            o.matrix_parent_inverse = Matrix.Translation(-CENTER)
    bm = board_materials()
    leds = {}
    for o in objs:
        if o.type != 'MESH':
            continue
        dn = o.data.name
        if dn.startswith('board_soldermask'):
            o.data.materials[0] = bm['mask']
        elif dn.startswith('board_silkscreen'):
            o.data.materials[0] = bm['silk']
        elif dn.startswith('board_pad'):
            o.data.materials[0] = bm['hasl']
        elif dn.startswith(('board_copper', 'board_via')):
            o.data.materials[0] = bm['copper']
            o.location.z += 0.00003
        elif dn.startswith('board_PCB'):
            o.data.materials[0] = bm['fr4']
        elif o.parent and o.parent.name in LEDS:
            leds[o.parent.name] = o
    for m in list(bpy.data.materials):
        if m.name.startswith('mat_'):
            component_material(m)
    # LED bodies get their own lit material (the shared mesh is copied first).
    for ref, o in leds.items():
        o.data = o.data.copy()
        for i, m in enumerate(o.data.materials):
            if m and m.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value > 0.5:
                o.data.materials[i] = led_material(LEDS[ref])

    # Raspberry Pi 4 under the board, plugged into J2.
    pobjs = import_glb(BUILD / 'pi4.glb')
    # Pi GLB frame (mm): x = long axis (SD end 0), y = component side up,
    # z = short axis + 1.6. Target: Pi short axis along board x, flush with
    # the right edge; long axis along board y, USB end 20 mm over the back.
    rot = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    off = Vector(((189.46) * MM, -86.5 * MM, PI_DROP * MM)) - CENTER
    for o in pobjs:
        if o.parent is None:
            o.parent = pi
            o.matrix_parent_inverse = Matrix.Translation(off) @ rot
    pi_mat = {
        'mat_0': principled('pi_pcb', (0.015, 0.20, 0.07), rough=0.3, coat=0.5),
        'mat_1': principled('pi_metal', (0.80, 0.80, 0.80), metallic=1, rough=0.28),
        'mat_2': principled('pi_black', (0.012, 0.012, 0.014), rough=0.4, coat=0.1),
    }
    for o in pobjs:
        if o.type == 'MESH':
            for i, m in enumerate(o.data.materials):
                if m and m.name.rsplit('.', 1)[0] in pi_mat and '.' in m.name:
                    o.data.materials[i] = pi_mat[m.name.rsplit('.', 1)[0]]
    return hat, pi


def studio(dark=True):
    sc = bpy.context.scene
    w = bpy.data.worlds.new('studio'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.012, 0.013, 0.015, 1)
    bg.inputs['Strength'].default_value = 1.0
    # Ground: one big matte graphite plane, reads on dark and light pages.
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, PI_DROP * MM - 0.0016 - 0.0002))
    g = bpy.context.object; g.name = 'ground'
    gm = principled('ground', (0.030, 0.032, 0.036), rough=0.6, spec=0.25)
    g.data.materials.append(gm)
    return g


def area(name, loc, target, size, energy, colour=(1, 1, 1), shape='RECTANGLE', size_y=None):
    l = bpy.data.lights.new(name, 'AREA'); l.energy = energy; l.color = colour
    l.shape = shape; l.size = size; l.size_y = size_y or size
    o = bpy.data.objects.new(name, l); bpy.context.scene.collection.objects.link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def lights(kind):
    if kind == 'top':
        area('key', (-0.45, 0.30, 0.45), (0, 0, 0), 0.6, 9, size_y=0.4)
        area('fill', (0.45, -0.35, 0.40), (0, 0, 0), 0.6, 5, (0.92, 0.96, 1.0))
        area('rim', (0.0, -0.6, 0.25), (0, 0, 0), 0.5, 2)
        return
    area('key', (-0.45, -0.20, 0.50), (0, 0, 0), 0.40, 7, (1.0, 0.96, 0.90), size_y=0.25)
    area('fill', (0.55, -0.35, 0.25), (0, 0, 0), 0.5, 1.2, (0.85, 0.92, 1.0))
    area('rim', (0.45, 0.50, 0.18), (0, 0, 0), 0.30, 7, (0.80, 0.88, 1.0), size_y=0.08)
    area('top', (0.05, 0.10, 0.80), (0, 0, 0), 0.4, 1.2)


def camera(loc, target, lens, fstop=None, focus=None, ortho=None):
    c = bpy.data.cameras.new('cam'); o = bpy.data.objects.new('cam', c)
    bpy.context.scene.collection.objects.link(o); bpy.context.scene.camera = o
    c.lens = lens; c.sensor_width = 36; c.clip_start = 0.005; c.clip_end = 50
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if fstop:
        c.dof.use_dof = True; c.dof.aperture_fstop = fstop
        c.dof.focus_distance = focus if focus else d.length
    return o


def render_setup(w, h, samples):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    dev = 'CPU'
    for kind in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                dev = 'GPU'
                break
        except TypeError:
            continue
    sc.cycles.device = dev
    if dev == 'CPU':
        samples = max(32, samples // 3)
    print(f'render device: {dev} ({prefs.compute_device_type}), samples {samples}')
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 8; sc.cycles.transmission_bounces = 8
    sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
    sc.render.resolution_x = w; sc.render.resolution_y = h; sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 90
    sc.render.fps = 12


def focus_on(cam, target):
    e = bpy.data.objects.new('focus', None); bpy.context.scene.collection.objects.link(e)
    e.location = target; cam.data.dof.focus_object = e
    return e


def aim(o, target):
    d = Vector(target) - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def vertical(samples=64):
    lights('hero')
    render_setup(1080, 1920, samples)
    sc = bpy.context.scene
    sc.render.fps = 30
    sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.render.use_persistent_data = True


def smooth(t):
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- shots
def shot(name):
    hat, pi = build_scene()
    studio()
    pv = args.preview
    still = name in ('hero', 'top', 'detail')
    if name == 'hero':
        lights('hero')
        render_setup(1920, 1280, 256)
        loc = Vector((-0.225, -0.40, 0.27))
        camera(loc, (0.004, -0.004, -0.006), 70, fstop=6.3,
               focus=(loc - Vector((-0.02, -0.04, 0.004))).length)
    elif name == 'top':
        lights('top')
        render_setup(1800, 1800, 192)
        camera((0, 0.009, 0.9), (0, 0.009, 0), 50, ortho=0.176)
    elif name == 'detail':
        lights('hero')
        render_setup(1920, 1280, 256)
        # Front LED row, buttons at the right end.
        tgt = Vector((0.018, -0.054, 0.002))
        loc = tgt + Vector((-0.060, -0.150, 0.115))
        camera(loc, tgt, 100, fstop=6.3, focus=(loc - Vector((0.008, -0.060, 0.006))).length)
    elif name == 'orbit':
        lights('hero')
        render_setup(960, 720, 96)
        camera((0, -0.33, 0.20), (0, 0, -0.008), 58, fstop=11)
        for o in (hat, pi):
            o.parent = None
        piv = bpy.data.objects.new('turntable', None); bpy.context.scene.collection.objects.link(piv)
        hat.parent = piv; pi.parent = piv
        # Keyed on every frame, so interpolation never matters; frame 73
        # would equal frame 1 and is not rendered.
        for f in range(1, 74):
            piv.rotation_euler = (0, 0, 2 * math.pi * (f - 1) / 72)
            piv.keyframe_insert('rotation_euler', frame=f)
    elif name == 'explode':
        lights('hero')
        render_setup(960, 720, 96)
        camera((0.27, -0.36, 0.19), (0.004, 0.004, 0.012), 62, fstop=11)
        # The Pi stays on the ground; the HAT lifts off its header and back.
        # 0-1 s seated, 1-2.5 s up 45 mm, hold, 3.5-5 s back down, hold.
        for f in range(1, 74):
            t = (f - 1) / 12.0
            if t < 1.0: u = 0
            elif t < 2.5: u = smooth((t - 1.0) / 1.5)
            elif t < 3.5: u = 1
            elif t < 5.0: u = 1 - smooth((t - 3.5) / 1.5)
            else: u = 0
            hat.location = (0, 0, 0.045 * u)
            hat.keyframe_insert('location', frame=f)
    elif name == 'v_fly':
        # Low pass across the board, front-left to the digital side, focus riding ahead.
        vertical()
        cam = camera((0, 0, 0), (0, 0, 0), 30, fstop=2.8)
        foc = focus_on(cam, (0, 0, 0))
        n = VSHOTS[name]
        for f in range(1, n + 1):
            u = smooth((f - 1) / (n - 1))
            cam.location = Vector((-0.085, -0.150, 0.055)).lerp(Vector((0.060, -0.115, 0.080)), u)
            foc.location = Vector((-0.045, -0.035, 0.006)).lerp(Vector((0.035, 0.010, 0.006)), u)
            aim(cam, foc.location)
            cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
            foc.keyframe_insert('location', frame=f)
    elif name == 'v_led':
        # Macro slide along the front edge: CLIP, health, REC/BUSY/READY, then the two buttons.
        vertical()
        cam = camera((0, 0, 0), (0, 0, 0), 85, fstop=4)
        foc = focus_on(cam, (0, 0, 0))
        n = VSHOTS[name]
        for f in range(1, n + 1):
            u = smooth((f - 1) / (n - 1))
            tgt = Vector((-0.060, -0.056, 0.004)).lerp(Vector((0.045, -0.056, 0.004)), u)
            cam.location = tgt + Vector((-0.040, -0.105, 0.080))
            foc.location = tgt
            aim(cam, tgt)
            cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
            foc.keyframe_insert('location', frame=f)
    elif name == 'v_orbit':
        vertical()
        camera((0, -0.25, 0.175), (0, 0, -0.004), 35, fstop=8)
        for o in (hat, pi):
            o.parent = None
        piv = bpy.data.objects.new('turntable', None); bpy.context.scene.collection.objects.link(piv)
        hat.parent = piv; pi.parent = piv
        n = VSHOTS[name]
        for f in range(1, n + 1):  # a half turn, eased in and out
            piv.rotation_euler = (0, 0, math.radians(-30) + math.pi * smooth((f - 1) / (n - 1)))
            piv.keyframe_insert('rotation_euler', frame=f)
    elif name == 'v_explode':
        vertical()
        camera((0.175, -0.245, 0.150), (0.0, 0.004, 0.030), 35, fstop=8)
        n = VSHOTS[name]
        for f in range(1, n + 1):  # 0.5 s seated, 1.5 s up 55 mm, hold, 1.2 s back down, hold
            t = (f - 1) / 30.0
            if t < 0.5: u = 0
            elif t < 2.0: u = smooth((t - 0.5) / 1.5)
            elif t < 2.5: u = 1
            elif t < 3.7: u = 1 - smooth((t - 2.5) / 1.2)
            else: u = 0
            hat.location = (0, 0, 0.055 * u)
            hat.keyframe_insert('location', frame=f)
    sc = bpy.context.scene
    if name in VSHOTS:
        frames = BUILD / 'frames' / name
        frames.mkdir(parents=True, exist_ok=True)
        n = VSHOTS[name]
        sc.frame_start, sc.frame_end = 1, n
        bpy.ops.wm.save_as_mainfile(filepath=str(BUILD / f'{name}.blend'))
        a, b = (int(x) for x in args.frames.split(':')) if args.frames else (1, n)
        for f in ((1, n // 2, n) if pv else range(a, b + 1)):
            if (frames / f'{f:04}.png').exists() and not pv:
                continue
            sc.frame_set(f)
            sc.render.filepath = str(frames / (f'preview-{f:04}.png' if pv else f'{f:04}.png'))
            bpy.ops.render.render(write_still=True)
        return
    if still:
        if pv:
            sc.cycles.samples = max(16, sc.cycles.samples // 4)
            sc.render.resolution_percentage = 50
        MEDIA.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(BUILD / f'{name}.blend'))
        sc.render.filepath = str((BUILD / f'preview-{name}.png') if pv else (MEDIA / f'{name}.png'))
        bpy.ops.render.render(write_still=True)
        return
    frames = BUILD / 'frames' / name
    frames.mkdir(parents=True, exist_ok=True)
    sc.frame_start, sc.frame_end = 1, 72
    bpy.ops.wm.save_as_mainfile(filepath=str(BUILD / f'{name}.blend'))
    for f in ((1, 37) if pv else range(1, 73)):
        sc.frame_set(f)
        sc.render.filepath = str(frames / f'{f:04}.png')
        bpy.ops.render.render(write_still=True)
    if not pv:
        stamp = {'frames': 72, 'board_glb_sha256': hashlib.sha256((BUILD / 'board.glb').read_bytes()).hexdigest()}
        (frames / 'render.json').write_text(json.dumps(stamp, indent=1) + '\n')


for s in SHOTS:
    shot(s)
