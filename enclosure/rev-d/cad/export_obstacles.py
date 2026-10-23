"""Export the rev D HAT + Raspberry Pi 4 models to the enclosure frame, for check_fit.py.

    tools/capped blender -b --factory-startup --python enclosure/rev-d/cad/export_obstacles.py

Reads hardware/kicad/rev_d/render/build/{board,pi4}.glb (made by export_model.sh)
and writes enclosure/rev-d/build/obstacles.npz: one triangle mesh per KiCad
footprint (key = reference, e.g. 'C1'), 'HAT_PCB', and one per Raspberry Pi
mesh (key 'PI4/<n>'). Units mm; frame as spec/SPEC.md section 1 (origin board
front-left corner, z = 0 on the HAT top face).

GLB -> spec frame: x = X - 51.06, y = 157.5 + Yb, z = Zb - 1.6 (the GLB has the
HAT's copper side at z = 0). The Pi is placed exactly as render_rev_d.py does.
"""
import bpy, sys
import numpy as np
from pathlib import Path
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT / 'hardware/kicad/rev_d/render/build'
OUT = HERE.parent / 'build' / 'obstacles.npz'
MM = 0.001
PI_DROP = -11.0
BOARD_X0, BOARD_Y0 = 51.06, 21.5
CENTER = Vector(((BOARD_X0 + 70) * MM, -(BOARD_Y0 + 68) * MM, 0))

bpy.ops.wm.read_factory_settings(use_empty=True)


def imp(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


board = imp(BUILD / 'board.glb')
pi = imp(BUILD / 'pi4.glb')
# Pi placement copied from render_rev_d.py (there both are parented with -CENTER;
# here we only need the Pi relative to the raw board frame).
rot = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
off = Vector((189.46 * MM, -86.5 * MM, PI_DROP * MM))
for o in pi:
    if o.parent is None:
        o.matrix_world = Matrix.Translation(off) @ rot @ o.matrix_world
bpy.context.view_layer.update()


def tri_mesh(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    mw = o.matrix_world
    v = np.array([(mw @ vt.co)[:] for vt in me.vertices], dtype=np.float64) / MM
    f = np.array([t.vertices[:] for t in me.loop_triangles], dtype=np.int32)
    ev.to_mesh_clear()
    v[:, 0] -= BOARD_X0
    v[:, 1] += 157.5
    v[:, 2] -= 1.6
    return v, f


def owner_ref(o):
    p = o
    while p is not None:
        if p.type == 'EMPTY' and not p.name.startswith(('Node', '=>')):
            return p.name
        p = p.parent
    return None


groups = {}
for o in board:
    if o.type != 'MESH':
        continue
    dn = o.data.name
    if dn.startswith('board_PCB'):
        key = 'HAT_PCB'
    elif dn.startswith('board_'):
        continue  # copper/pad/silk/mask: films on the PCB faces
    else:
        key = owner_ref(o) or o.name
    groups.setdefault(key, []).append(tri_mesh(o))
for i, o in enumerate([o for o in pi if o.type == 'MESH']):
    groups.setdefault('PI4/%03d' % i, []).append(tri_mesh(o))

arrays = {}
for k, parts in groups.items():
    vs, fs, n = [], [], 0
    for v, f in parts:
        vs.append(v); fs.append(f + n); n += len(v)
    arrays[k + '|v'] = np.concatenate(vs)
    arrays[k + '|f'] = np.concatenate(fs)
OUT.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(OUT, **arrays)
allv = np.concatenate([arrays[k] for k in arrays if k.endswith('|v')])
print('EXPORTED', len(groups), 'groups to', OUT, 'bbox', allv.min(0).round(2), allv.max(0).round(2))
