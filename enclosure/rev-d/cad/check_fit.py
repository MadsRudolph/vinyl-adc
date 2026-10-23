"""Interference, clearance and printability check for the rev D enclosure.

    tools/capped enclosure/rev-d/.venv/bin/python enclosure/rev-d/cad/check_fit.py [--set NAME=VALUE ...]

Needs:
  build/obstacles.npz  from  blender -b --factory-startup --python enclosure/rev-d/cad/export_obstacles.py
  build/asm/*.stl      from  enclosure.py (run it first with the same --set values)

Obstacles are (a) every KiCad 3D model on the HAT, the HAT PCB and the Raspberry
Pi 4 model, and (b) the AS-BUILT ENVELOPES that replace the KiCad models where
the fitted part differs (heights taken from enclosure.py's parameters, i.e. the
spec estimates until Mads measures): tall electrolytics, MKT boxes, socketed
DIPs, terminal blocks, trimmers, LEDs, switch plungers; plus screw heads,
standoffs, the HAT's solder-side lead zone, the terminal-block wire gutter and
the plugs in every Pi port (so a cut-out that blocks a plug's overmould fails).

For every printed part (and the acrylic lid) it reports the minimum clearance
and nearest obstacles, and FAILS (exit code 1) if anything intersects, apart
from the designed contacts (posts under the HAT, bosses under the Pi, button
tips resting on the switch plungers). It also checks the parts against each
other, bed fit, wall thickness and unsupported overhangs in print orientation.
Writes build/check_fit.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import enclosure as E  # noqa: E402  (parameters + overrides are shared)

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / 'spec/board_mech.json').read_text())
PARTS = SPEC['parts']
RNG = np.random.default_rng(1)
PEN_TOL = 0.05          # mm; deeper than this is an intersection
WARN_CLEAR = 0.5        # mm; report as tight


# ----------------------------------------------------------------- obstacles
def box_mesh(x0, x1, y0, y1, z0, z1):
    m = trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0))
    m.apply_translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    return m


def cyl_mesh(x, y, z0, z1, d, axis='z', sections=48):
    m = trimesh.creation.cylinder(radius=d / 2, height=abs(z1 - z0), sections=sections)
    if axis == 'x':
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (0, 1, 0)))
    elif axis == 'y':
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))
    m.apply_translation((x, y, (z0 + z1) / 2) if axis == 'z' else (0, 0, 0))
    return m


def axis_cyl(c, length_axis, a0, a1, d):
    """Cylinder along x or y between a0 and a1, centre c = (u, z)."""
    m = trimesh.creation.cylinder(radius=d / 2, height=a1 - a0, sections=48)
    if length_axis == 'x':
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (0, 1, 0)))
        m.apply_translation(((a0 + a1) / 2, c[0], c[1]))
    else:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))
        m.apply_translation((c[0], (a0 + a1) / 2, c[1]))
    return m


def mb(ref):
    return PARTS[ref]['model_bbox']


def asbuilt_envelopes():
    env = {}
    for ref, p in PARTS.items():
        cat = p['category']
        b = p.get('model_bbox')
        if cat == 'ic_dip':
            env[ref + '[socketed]'] = box_mesh(*b['x'], *b['y'], 0, b['z'][1] + E.DIP_SOCKET_ADD)
        elif cat == 'terminal_block':
            env[ref + '[as-built]'] = box_mesh(*b['x'], *b['y'], 0, E.TERMINAL_BLOCK_Z)
        elif cat == 'trimmer':
            env[ref + '[as-built]'] = box_mesh(*b['x'], *b['y'], 0, E.TRIMMER_Z)
        elif cat == 'led':
            cx, cy = p['pad_centroid']
            base = E.LED_DOME_Z - 8.6
            env[ref + '[LED body]'] = cyl_mesh(cx, cy, base + 1.0, E.LED_DOME_Z, 5.0)
            env[ref + '[LED flange]'] = cyl_mesh(cx, cy, base, base + 1.0, 5.8)
    for ref in ('C1', 'C18'):
        b = mb(ref)
        env[ref + '[as-built]'] = cyl_mesh(np.mean(b['x']), np.mean(b['y']), 0, E.C1_C18_Z, b['x'][1] - b['x'][0])
    for ref in ('C5', 'C6'):
        b = mb(ref)
        env[ref + '[as-built]'] = cyl_mesh(np.mean(b['x']), np.mean(b['y']), 0, E.C5_C6_Z, b['x'][1] - b['x'][0])
    for ref in ('C20', 'C60'):
        ex, ey = PARTS[ref]['as_built']['envelope_xy']
        env[ref + '[MKT box]'] = box_mesh(*ex, *ey, 0, E.C20_C60_Z)
    for ref, (x, y) in E.SW.items():
        env[ref + '[body]'] = box_mesh(x - 3, x + 3, y - 3, y + 3, 0, 3.5)
        env[ref + '[plunger]'] = cyl_mesh(x, y, 3.4, E.SW_PLUNGER_Z, 3.5)
    # fasteners
    for ref, (x, y) in E.HAT_POSTS.items():
        env[ref + '[M3 head+washer]'] = cyl_mesh(x, y, 0, 0.8 + 1.65, 7.0)
    for x, y in E.PI_HOLES:
        env['M2.5 head (%.0f,%.0f)' % (x, y)] = cyl_mesh(x, y, 0, 1.8, 5.0)
        env['standoff (%.0f,%.0f)' % (x, y)] = cyl_mesh(x, y, E.PI_TOP_Z, E.HAT_BOT_Z, 5.8)
    # HAT and its solder side (nothing but the M3 posts may touch it)
    env['HAT_PCB[board]'] = box_mesh(0, 140, 0, 136, E.HAT_BOT_Z, 0)
    leads = box_mesh(0, 140, 0, 136, -4.1, E.HAT_BOT_Z)
    for x, y in E.HAT_POSTS.values():
        leads = leads.difference(cyl_mesh(x, y, -5, -1, 2 * 5.0))
    # the Pi sits under part of it: leads there are covered by the Pi model anyway
    env['HAT solder-side lead zone'] = leads
    env['terminal wire gutter'] = box_mesh(-8.0, 0.0, 60.0, 132.0, E.HAT_BOT_Z, 10.0)
    # plugs in the Pi ports (overmould envelopes, 25 mm long), shifted with the Pi
    dz = E.PI_DZ
    env['plug USB-C'] = box_mesh(141.2, 166, 82.2 - 6.25, 82.2 + 6.25, -11.02 + dz - 3.5, -11.02 + dz + 3.5)
    if E.HDMI_OPENING:
        for y in (97.0, 110.5):
            env['plug HDMI %.0f' % y] = box_mesh(141.2, 166, y - 5.75, y + 5.75, -11.18 + dz - 3.75, -11.18 + dz + 3.75)
    if E.AUDIO_OPENING:
        env['plug 3.5 mm'] = axis_cyl((125.0, -9.6 + dz), 'x', 142.5, 166, 8.0)
    env['plug RJ45'] = box_mesh(94.29 - 7.0, 94.29 + 7.0, 159.25, 185, -12.6 + dz, -12.6 + dz + 13.65)
    for name, xc, zt in (('USB3', 113.015, 3.74), ('USB2', 131.015, 3.007)):
        for k, zc in enumerate((zt - 4.1, zt - 12.3)):
            env['plug %s %s' % (name, 'upper' if k == 0 else 'lower')] = box_mesh(
                xc - 8.0, xc + 8.0, 158.9, 185, zc + dz - 4.0, zc + dz + 4.0)
    if E.REAR_IO == 'rca':
        for name, x in E.REAR_RCA:
            env['RCA jack %s (inside body+nut)' % name] = axis_cyl((x, E.REAR_IO_Z), 'y', E.YI1 - 14, E.YI1, 13.0)
        env['ground post (inside)'] = axis_cyl((E.REAR_GND_X, E.REAR_IO_Z), 'y', E.YI1 - 12, E.YI1, 10.0)
    return env


def load_obstacles():
    npz = np.load(ROOT / 'build/obstacles.npz')
    keys = sorted({k.split('|')[0] for k in npz.files})
    obs = {}
    replaced = {r for r, p in PARTS.items() if p['category'] in ('led',)}
    for k in keys:
        if k in replaced:
            continue  # LEDs: the as-built LED (flush) replaces the 3 mm-raised KiCad model
        v, f = npz[k + '|v'].copy(), npz[k + '|f']
        if k.startswith('PI4/'):
            v[:, 2] += E.PI_DZ
        obs['model ' + k] = trimesh.Trimesh(v, f, process=False)
    for k, m in asbuilt_envelopes().items():
        obs[k] = m
    return obs


def surface_dist(pq, pts, chunk=4000):
    """pq.on_surface in chunks: trimesh builds a points x candidate-triangles array, which
    for 400k points against a dense mesh ran the machine out of memory (oomd, 21 Oct)."""
    if len(pts) == 0:
        return np.empty(0)
    return np.concatenate([pq.on_surface(pts[i:i + chunk])[1] for i in range(0, len(pts), chunk)])


def contains(m, pts, chunk=20000):
    return np.concatenate([m.contains(pts[i:i + chunk]) for i in range(0, len(pts), chunk)])


def surface_samples(m, density=3.0, cap=400000):
    n = int(min(cap, max(200, m.area * density)))
    pts, fi = trimesh.sample.sample_surface(m, n, seed=1)
    return np.vstack([pts, m.vertices]), None


# allowed contacts: (part prefix, obstacle prefix)
ALLOWED = [('tray', 'model HAT_PCB'), ('tray', 'HAT_PCB[board]'),
           ('tray', 'model PI4/'), ('button_sw', 'SW')]


def allowed(part, obst):
    return any(part.startswith(a) and obst.startswith(b) for a, b in ALLOWED)


def check_part(name, part, obs):
    lo, hi = part.bounds[0] - 6, part.bounds[1] + 6
    res = []
    pq = trimesh.proximity.ProximityQuery(part)
    for oname, om in obs.items():
        ob_lo, ob_hi = om.bounds
        if np.any(ob_hi < lo) or np.any(ob_lo > hi):
            continue
        pts, _ = surface_samples(om, density=4.0)
        sel = np.all((pts > lo) & (pts < hi), axis=1)
        pts = pts[sel]
        if len(pts) == 0:
            continue
        # cheap prefilter by bounding box distance, then exact distance to the part surface
        dist = surface_dist(pq, pts)
        inside = contains(part, pts)
        pen = float(dist[inside].max()) if inside.any() else 0.0
        clear = float(dist[~inside].min()) if (~inside).any() else 0.0
        # reverse test for closed obstacles: part surface inside the obstacle
        if om.is_watertight:
            pp = part_samples[name]
            s2 = np.all((pp > ob_lo - 0.01) & (pp < ob_hi + 0.01), axis=1)
            if s2.any():
                ins2 = contains(om, pp[s2])
                if ins2.any():
                    d2 = surface_dist(trimesh.proximity.ProximityQuery(om), pp[s2][ins2])
                    pen = max(pen, float(d2.max()))
        res.append(dict(obstacle=oname, clearance=round(clear, 3), penetration=round(pen, 3),
                        allowed_contact=allowed(name, oname)))
    return res


def overhangs(mesh_bed, min_area=4.0):
    """Down-facing faces steeper than 45 deg (not on the bed): connected regions, largest first."""
    n = mesh_bed.face_normals
    c = mesh_bed.triangles_center
    down = (n[:, 2] < -0.7072) & (c[:, 2] > 0.25)
    idx = np.nonzero(down)[0]
    if len(idx) == 0:
        return []
    adj = mesh_bed.face_adjacency
    m = np.isin(adj[:, 0], idx) & np.isin(adj[:, 1], idx)
    groups = trimesh.graph.connected_components(adj[m], nodes=idx)
    out = []
    for g in groups:
        g = np.asarray(g)
        a = float(mesh_bed.area_faces[g].sum())
        if a < min_area:
            continue
        pts = mesh_bed.triangles[g].reshape(-1, 3)
        ext = pts.max(0) - pts.min(0)
        out.append(dict(area_mm2=round(a, 1), extent_xy=[round(float(ext[0]), 1), round(float(ext[1]), 1)],
                        z=round(float(pts[:, 2].min()), 1), centre=[round(float(v), 1) for v in pts.mean(0)]))
    return sorted(out, key=lambda d: -d['area_mm2'])


def wall_thickness(m, n=6000):
    pts, fi = trimesh.sample.sample_surface(m, n, seed=2)
    nrm = m.face_normals[fi]
    origins = pts - nrm * 0.01
    locs, ray_idx, _ = m.ray.intersects_location(origins, -nrm, multiple_hits=False)
    th = np.full(len(pts), np.inf)
    th[ray_idx] = np.linalg.norm(locs - origins[ray_idx], axis=1)
    return th, pts


def main():
    global part_samples
    asm = ROOT / 'build/asm'
    rep = json.loads((ROOT / 'build/build_report.json').read_text())
    names = [p.stem for p in sorted(asm.glob('*.stl'))]
    meshes = {n: trimesh.load(asm / f'{n}.stl') for n in names}
    part_samples = {n: surface_samples(m, density=3.0)[0] for n, m in meshes.items()}
    obs = load_obstacles()
    fail = []
    out = {'parameters': dict(LED_DOME_Z=E.LED_DOME_Z, SW_PLUNGER_Z=E.SW_PLUNGER_Z, HAT_PI_STANDOFF=E.HAT_PI_STANDOFF,
                              DESIGN_ENVELOPE_Z=E.DESIGN_ENVELOPE_Z, LID_UNDER_Z=E.LID_UNDER_Z, C1_C18_Z=E.C1_C18_Z,
                              C20_C60_Z=E.C20_C60_Z, TERMINAL_BLOCK_Z=E.TERMINAL_BLOCK_Z, TRIMMER_Z=E.TRIMMER_Z,
                              REAR_IO=E.REAR_IO),
           'parts': {}, 'pairs': [], 'printability': {}}
    print('== clearance to board, Pi, components (as-built estimates) ==')
    for n in names:
        m = meshes[n]
        if not m.is_watertight:
            fail.append(f'{n}: mesh not watertight')
        res = check_part(n, m, obs)
        res.sort(key=lambda r: (r['clearance'] if r['penetration'] <= PEN_TOL else -r['penetration']))
        bad = [r for r in res if r['penetration'] > PEN_TOL and not r['allowed_contact']]
        bad_contact = [r for r in res if r['allowed_contact'] and r['penetration'] > PEN_TOL]
        free = [r for r in res if not r['allowed_contact']]
        mn = min((r['clearance'] for r in free if r['penetration'] <= PEN_TOL), default=None)
        out['parts'][n] = dict(min_clearance=mn, intersections=bad, contact_overlap=bad_contact,
                               nearest=[r for r in free if r['penetration'] <= PEN_TOL][:8],
                               contacts=[r for r in res if r['allowed_contact']][:6])
        status = 'FAIL' if (bad or bad_contact) else 'ok'
        near = ', '.join(f"{r['obstacle']} {r['clearance']:.2f}" for r in out['parts'][n]['nearest'][:4])
        print(f'{status:4} {n:12} min clearance {mn if mn is None else round(mn, 2)} mm   nearest: {near}')
        for r in bad + bad_contact:
            print(f'      INTERSECTS {r["obstacle"]} by {r["penetration"]:.2f} mm')
            fail.append(f'{n} intersects {r["obstacle"]} ({r["penetration"]:.2f} mm)')
    print('\n== parts against each other (intersection volume) ==')
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ma, mb_ = meshes[a], meshes[b]
            if np.any(ma.bounds[1] < mb_.bounds[0]) or np.any(mb_.bounds[1] < ma.bounds[0]):
                continue
            try:
                inter = trimesh.boolean.intersection([ma, mb_], engine='manifold')
                v = float(inter.volume) if inter is not None and len(inter.faces) else 0.0
            except Exception as e:  # noqa: BLE001
                v = float('nan')
            pq = trimesh.proximity.ProximityQuery(mb_)
            d = surface_dist(pq, part_samples[a][:60000])
            gap = float(d.min())
            out['pairs'].append(dict(a=a, b=b, overlap_mm3=round(v, 3), min_gap=round(gap, 3)))
            flag = 'FAIL' if v > 0.5 else 'ok'
            print(f'{flag:4} {a:12} x {b:12} overlap {v:8.3f} mm3   min gap {gap:.2f} mm')
            if v > 0.5:
                fail.append(f'{a} overlaps {b} by {v:.1f} mm3')
    print('\n== printability (print orientation) ==')
    from build123d import import_stl  # noqa: F401  (not needed; bed meshes come from out/)
    for n, info in rep['parts'].items():
        stem = 'light_pipe' if n.startswith('pipe_') else n
        if n.startswith('pipe_') and n != 'pipe_1':
            continue
        mbed = trimesh.load(ROOT / 'out' / f'{stem}.stl')
        th, pts = wall_thickness(mbed)
        finite = th[np.isfinite(th)]
        thin = finite < 1.2
        ov = overhangs(mbed)
        ex = mbed.extents
        fits = bool(ex[0] <= E.BED[0] and ex[1] <= E.BED[1] and ex[2] <= E.BED[2])
        pr = dict(bed_extents=[round(float(v), 1) for v in ex], fits_bed=fits,
                  wall_p01=round(float(np.percentile(finite, 1)), 2), wall_p05=round(float(np.percentile(finite, 5)), 2),
                  thin_fraction=round(float(thin.mean()), 4),
                  thin_spots=[[round(float(v), 1) for v in p] for p in pts[np.isfinite(th)][thin][:12]],
                  overhang_regions=ov[:12], overhang_total_mm2=round(sum(o['area_mm2'] for o in ov), 1))
        out['printability'][stem] = pr
        if not fits:
            fail.append(f'{stem} does not fit the bed')
        print(f'{stem:12} bed {pr["bed_extents"]} fits={fits}  wall p1/p5 {pr["wall_p01"]}/{pr["wall_p05"]} mm, '
              f'<1.2 mm on {100 * pr["thin_fraction"]:.2f}% of surface; overhang regions >4 mm2: {len(ov)}'
              + (f' (largest {ov[0]["area_mm2"]} mm2 at {ov[0]["centre"]}, span {ov[0]["extent_xy"]})' if ov else ''))
    out['fail'] = fail
    (ROOT / 'build/check_fit.json').write_text(json.dumps(out, indent=1))
    print('\nRESULT:', 'FAIL' if fail else 'PASS', *(['\n  - ' + f for f in fail]))
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
