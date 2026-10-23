#!/usr/bin/env python3
"""Extract the mechanical description of the rev D HAT (+ Raspberry Pi 4) for the enclosure.

    python extract_board_mech.py            # writes board_mech.json and top_overlay.png here

Needs pcbnew (KiCad 10), trimesh, numpy and Pillow. A venv made with
`python3 -m venv --system-site-packages venv && venv/bin/pip install trimesh numpy pillow`
sees KiCad's pcbnew and the pip packages together.

Inputs (repo-relative):
  hardware/kicad/rev_d/vinyl_adc_rev_d.kicad_pcb    footprints, pads, holes, outline
  hardware/kicad/rev_d/render/build/board.glb        3D model heights (kicad-cli export)
  hardware/kicad/rev_d/render/build/pi4.glb          Raspberry Pi 4B model (FreeCAD library)
  media/showcase/rev-d/top.png                       orthographic top render (overlay base)

Board frame used everywhere in the output (mm):
  origin = board lower-left corner seen from above with the LED edge at the bottom,
  x -> right, y -> toward the back (the Pi's USB/Ethernet end), z up,
  z = 0 on the top face of the HAT (component side, F.Cu); HAT bottom face z = -1.6.
  KiCad page coordinates map as  x = X - 51.06,  y = 157.5 - Y.
"""
import json, math, pathlib
import numpy as np
import pcbnew
import trimesh
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
PCB = REPO / 'hardware/kicad/rev_d/vinyl_adc_rev_d.kicad_pcb'
BOARD_GLB = REPO / 'hardware/kicad/rev_d/render/build/board.glb'
PI_GLB = REPO / 'hardware/kicad/rev_d/render/build/pi4.glb'
TOP_PNG = REPO / 'media/showcase/rev-d/top.png'

X0, Y1 = 51.06, 157.5          # page coords of the board's lower-left corner
W, D, T = 140.0, 136.0, 1.6
PI_DROP = -11.0                # Pi PCB top below the HAT bottom face (render_rev_d.py)
Z_PI_TOP = -T + PI_DROP        # -12.6 in board frame


def bx(X): return round(X - X0, 3)
def by(Y): return round(Y1 - Y, 3)
def r3(v): return round(float(v), 3)


# ------------------------------------------------------------------ 3D vertex clouds
def cloud(path):
    s = trimesh.load(path)
    out = []
    for n in s.graph.nodes_geometry:
        Tm, g = s.graph[n]
        v = trimesh.transform_points(s.geometry[g].vertices, Tm) * 1000.0
        out.append((g, v))
    return out

board_parts = cloud(BOARD_GLB)
# board.glb: x = page X, y = up (HAT bottom face 0, top 1.6), z = page Y
comp = np.vstack([v for g, v in board_parts if not g.startswith('board_')])
CB = np.c_[comp[:, 0] - X0, Y1 - comp[:, 2], comp[:, 1] - T]       # board frame
pi = np.vstack([v for g, v in cloud(PI_GLB)])
# pi4.glb: L = long axis (SD end 0, USB end 85), S = short axis (port edge +1.62),
# H = -gz = height above the Pi PCB top. Placement (render_rev_d.py):
#   board x = S + 138.40, board y = L + 71.0, z = H + Z_PI_TOP
PL, PS, PH = pi[:, 0], pi[:, 1], -pi[:, 2]
PI_X = lambda S: S + (189.46 - X0)
PI_Y = lambda L: L + (Y1 - 86.5)
PI_Z = lambda H: H + Z_PI_TOP


def pi_box(mask):
    return dict(x=[r3(PI_X(PS[mask].min())), r3(PI_X(PS[mask].max()))],
                y=[r3(PI_Y(PL[mask].min())), r3(PI_Y(PL[mask].max()))],
                z=[r3(PI_Z(PH[mask].min())), r3(PI_Z(PH[mask].max()))])


# ------------------------------------------------------------------ PCB
b = pcbnew.LoadBoard(str(PCB))
mm = pcbnew.ToMM

all_pads = []
for f in b.GetFootprints():
    for p in f.Pads():
        q = p.GetPosition()
        all_pads.append((f.GetReference(), bx(mm(q.x)), by(mm(q.y)),
                         mm(p.GetSize(pcbnew.F_Cu).x), mm(p.GetSize(pcbnew.F_Cu).y), p.GetAttribute()))
tracks = []
for t in b.GetTracks():
    if t.GetClass() in ('PCB_TRACK', 'PCB_ARC'):
        s, e = t.GetStart(), t.GetEnd()
        tracks.append((bx(mm(s.x)), by(mm(s.y)), bx(mm(e.x)), by(mm(e.y)), mm(t.GetWidth()), t.GetLayerName()))


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    u = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - u * dx, py - y1 - u * dy)


def clear_radius(x, y, own=None):
    """Distance from (x, y) to the nearest copper (pad edge or track edge) not belonging to `own`."""
    d_pad = min(math.hypot(px - x, py - y) - max(sx, sy) / 2
                for r, px, py, sx, sy, a in all_pads if r != own and a != 3)
    d_trk = min(seg_dist(x, y, *t[:4]) - t[4] / 2 for t in tracks) if tracks else 99
    return r3(d_pad), r3(d_trk)


# zones: report which layers carry pours (keep-outs around NPTH are set by zone clearance)
zone_layers = sorted({z.GetLayerName() for z in b.Zones()})

LED_LABEL = {'D6': 'CLIP L', 'D7': 'CLIP R', 'D3': '+5VA', 'D4': '-5V', 'D5': 'CLK',
             'D8': 'REC', 'D9': 'BUSY', 'D10': 'READY'}
LED_GPIO = {'D8': 'GPIO17', 'D9': 'GPIO27', 'D10': 'GPIO22'}

# As-built corrections where the KiCad 3D model is known not to match the parts Mads fitted
# (from media/showcase/rev-d/photos/*.jpg; none of these are measured -- see SPEC.md checklist).
ASBUILT = {
    'LED':  dict(z_top_est=8.7, z_top_range=[8.6, 11.6],
                 note='Photos show the 5 mm LEDs seated flush (flange on the board): 8.6 mm body + ~0.1. '
                      'The KiCad model floats them 3 mm (top 11.59). MEASURE all eight.'),
    'C20':  dict(z_top_est=16.0, envelope_xy=[[6.5, 25.5], [96.5, 111.0]],
                 note='Fitted part is a Philips/BC MKT 373 1.5 uF 100 V box, much larger than the 11 x 6.3 '
                      'footprint; it sits over the RV20/terminal side. Envelope estimated from photos. MEASURE.'),
    'C60':  dict(z_top_est=16.0, envelope_xy=[[6.5, 25.5], [38.5, 53.0]],
                 note='As C20 (MKT 373 1.5 uF box). MEASURE.'),
    'C1':   dict(z_top_est=17.0, z_top_range=[12.5, 20.0],
                 note='470 uF, blue sleeve, visibly taller than its 10 mm diameter (photo). MEASURE.'),
    'C18':  dict(z_top_est=17.0, z_top_range=[12.5, 20.0], note='470 uF, black. MEASURE.'),
    'C5':   dict(z_top_est=13.0, z_top_range=[11.5, 16.0], note='220 uF 8 mm. MEASURE.'),
    'C6':   dict(z_top_est=13.0, z_top_range=[11.5, 16.0], note='220 uF 8 mm. MEASURE.'),
    'RV20': dict(z_top_est=12.0, note='Trimmer body type not visible in photos (footprint is a 1x3 '
                                      'horizontal header). Reserve 12 mm, screwdriver from the top with the lid off.'),
    'RV60': dict(z_top_est=12.0, note='As RV20.'),
    'SW1':  dict(z_top_est=5.0, z_top_range=[4.3, 9.5],
                 note='6 x 6 mm tact switch; model plunger top 4.3. Real plunger height depends on the '
                      'variant fitted (4.3/5/7/9.5 mm). MEASURE before cutting button stems.'),
    'SW2':  dict(z_top_est=5.0, z_top_range=[4.3, 9.5], note='As SW1.'),
    'DIP':  dict(z_add_socket=4.5,
                 note='Many DIPs are in turned-pin sockets (bring-up log): add ~4.5 mm (socket + seat) to the model height.'),
    'TB':   dict(note='Model is a Phoenix MKDS substitute (13.8 mm). The fitted green DTU 2-pole blocks look '
                      '~10-11 mm; 13.8 kept as the conservative envelope. Wire entry faces -x (left edge), '
                      'screw heads face +z.'),
}


def category(ref, fp):
    if ref.startswith('H'): return 'mounting_hole'
    if fp.startswith('LED'): return 'led'
    if fp.startswith('SW_'): return 'switch'
    if fp.startswith('TerminalBlock'): return 'terminal_block'
    if ref.startswith('RV'): return 'trimmer'
    if ref == 'J2': return 'pi_socket'
    if fp.startswith('PinHeader'): return 'pin_header'
    if fp.startswith('DIP'): return 'ic_dip'
    if fp.startswith('CP_'): return 'electrolytic'
    if fp.startswith('C_Rect'): return 'film_cap_box'
    if fp.startswith('L_'): return 'inductor'
    if fp.startswith('Crystal'): return 'crystal'
    if fp.startswith('TO-92'): return 'transistor'
    if fp.startswith('D_'): return 'diode'
    if fp.startswith('C_Disc'): return 'ceramic_cap'
    if fp.startswith('R_'): return 'resistor'
    return 'other'


def nearest_edge(x0, x1, y0, y1):
    d = {'front(y=0)': y0, 'back(y=136)': D - y1, 'left(x=0)': x0, 'right(x=140)': W - x1}
    k = min(d, key=d.get)
    return k, r3(d[k])


parts = {}
for f in b.GetFootprints():
    ref = f.GetReference()
    fp = f.GetFPIDAsString().split(':')[-1]
    cat = category(ref, fp)
    flipped = f.IsFlipped()
    cy = f.GetCourtyard(pcbnew.B_CrtYd if flipped else pcbnew.F_CrtYd)
    try:
        bb = cy.BBox()
        L_, R_, T_, B_ = (mm(v) for v in (bb.GetLeft(), bb.GetRight(), bb.GetTop(), bb.GetBottom()))
    except Exception:
        bb = f.GetBoundingBox(False)
        L_, R_, T_, B_ = (mm(v) for v in (bb.GetLeft(), bb.GetRight(), bb.GetTop(), bb.GetBottom()))
    cx0, cx1, cy0, cy1 = bx(L_), bx(R_), by(B_), by(T_)
    pads = [(bx(mm(p.GetPosition().x)), by(mm(p.GetPosition().y))) for p in f.Pads()]
    pc = (r3(np.mean([p[0] for p in pads])), r3(np.mean([p[1] for p in pads]))) if pads else None
    # model height from the GLB, vertices inside the courtyard (shrunk 0.4 mm against neighbours)
    sh = 0.4
    m = (CB[:, 0] > cx0 + sh) & (CB[:, 0] < cx1 - sh) & (CB[:, 1] > cy0 + sh) & (CB[:, 1] < cy1 - sh)
    m &= (CB[:, 2] < -T) if flipped else (CB[:, 2] > 0)
    mb = None
    if m.sum():
        P = CB[m]
        mb = dict(x=[r3(P[:, 0].min()), r3(P[:, 0].max())], y=[r3(P[:, 1].min()), r3(P[:, 1].max())],
                  z=[r3(P[:, 2].min()), r3(P[:, 2].max())])
    p = f.GetPosition()
    e, ed = nearest_edge(cx0, cx1, cy0, cy1)
    d = dict(value=f.GetValue().strip(), footprint=fp, category=cat,
             anchor=[bx(mm(p.x)), by(mm(p.y))], rot_deg=f.GetOrientationDegrees(),
             side='bottom' if flipped else 'top', pad_centroid=list(pc) if pc else None,
             courtyard={'x': [cx0, cx1], 'y': [cy0, cy1]},
             model_bbox=mb, nearest_edge=e, edge_distance=ed)
    if cat == 'ic_dip':
        d['as_built'] = dict(z_top_est=r3(mb['z'][1] + ASBUILT['DIP']['z_add_socket']), note=ASBUILT['DIP']['note'])
    if cat == 'terminal_block':
        d['as_built'] = dict(z_top_est=13.8, wire_entry_face='-x (left edge)', note=ASBUILT['TB']['note'])
    if cat == 'led':
        d['as_built'] = ASBUILT['LED']
    if ref in ASBUILT:
        d['as_built'] = ASBUILT[ref]
    if ref == 'D15':   # neighbour terminal block leaks into its courtyard; same part as D16
        d['model_bbox']['z'][1] = 3.2
    parts[ref] = d

# ------------------------------------------------------------------ LEDs and switches
leds = []
for ref in sorted(LED_LABEL, key=lambda r: parts[r]['pad_centroid'][0]):
    p = parts[ref]
    cx, cy = p['pad_centroid']
    leds.append(dict(ref=ref, label=LED_LABEL[ref], colour=p['value'], gpio=LED_GPIO.get(ref),
                     centre=[cx, cy], body_dia=5.0, flange_dia=5.8, flange_flat='cathode side (pad 1, -x)',
                     model_z_top=p['model_bbox']['z'][1], z_top_est=ASBUILT['LED']['z_top_est'],
                     z_top_range=ASBUILT['LED']['z_top_range']))
pitch = np.diff([l['centre'][0] for l in leds])
switches = []
for ref, label, gpio in (('SW1', 'SHUTDOWN / WAKE', 'GPIO3'), ('SW2', 'USER', 'GPIO23')):
    p = parts[ref]
    switches.append(dict(ref=ref, label=label, gpio=gpio, centre=p['pad_centroid'],
                         body=[6.0, 6.0], body_height=3.5, actuator_dia=3.5,
                         model_actuator_z_top=p['model_bbox']['z'][1],
                         z_top_est=ASBUILT['SW1']['z_top_est'], z_top_range=ASBUILT['SW1']['z_top_range'],
                         travel=0.25, actuation_force_gf='160-260 (typical 6 mm tact)',
                         pads=[[r3(x), r3(y)] for x, y in
                               [(pp[1], pp[2]) for pp in all_pads if pp[0] == ref]]))

# ------------------------------------------------------------------ holes
holes = []
for f in b.GetFootprints():
    ref = f.GetReference()
    if not ref.startswith('H'): continue
    pad = list(f.Pads())[0]
    q = pad.GetPosition()
    x, y = bx(mm(q.x)), by(mm(q.y))
    dr = r3(mm(pad.GetDrillSize().x))
    dp, dt = clear_radius(x, y, own=ref)
    holes.append(dict(ref=ref, x=x, y=y, drill=dr, plated=pad.GetAttribute() != 3,
                      thread='M3' if dr > 3 else 'M2.5',
                      role='HAT-to-enclosure' if dr > 3 else 'Pi 4 stack (HAT + Pi share this hole axis)',
                      copper_clear_radius_pads=dp, copper_clear_radius_tracks=dt,
                      max_head_or_washer_dia=r3(2 * min(dp, dt) - 0.6)))

# ------------------------------------------------------------------ Raspberry Pi 4
pcbm = (PH > -1.61) & (PH < 0.01) & (PL > -0.01) & (PL < 85.01) & (PS > -54.4) & (PS < 1.63)
pi_pcb = pi_box(pcbm)


def face_group(mask, axis_vals, gap=1.0):
    v = np.sort(np.unique(np.round(axis_vals[mask], 1)))
    g = [[v[0]]]
    for a in v[1:]:
        (g[-1].append(a) if a - g[-1][-1] <= gap else g.append([a]))
    return [(a[0], a[-1]) for a in g]


right = PS > 1.65
def rbox(l0, l1, extra=0.0):
    msk = (PL >= l0) & (PL <= l1) & (PS > -9) & (PH > -0.2)
    return pi_box(msk)

pi_ports = []
# Right-edge (board x = 140) ports. Centres from the Raspberry Pi 4B mechanical drawing,
# verified against the model (USB-C 11.2, HDMI0 26.0, HDMI1 39.5, audio 54.0 from the SD end).
for name, Lc, w, h, plug in (('USB-C power', 11.2, 9.0, 3.2, [12.5, 7.0]),
                             ('micro-HDMI 0', 26.0, 6.5, 3.0, [11.5, 7.5]),
                             ('micro-HDMI 1', 39.5, 6.5, 3.0, [11.5, 7.5]),
                             ('3.5 mm audio/composite', 54.0, 6.0, 6.0, [8.0, 8.0])):
    msk = right & (np.abs(PL - Lc) < w / 2 + 0.3)
    face = r3(PI_X(PS[msk].max()))
    zc = r3(PI_Z(PH[msk & (PH > -0.2)].min() + PH[msk].max()) / 2) if False else r3((PI_Z(max(PH[msk].min(), 0)) + PI_Z(PH[msk].max())) / 2)
    pi_ports.append(dict(name=name, faces='right (+x)', centre=[face, r3(PI_Y(Lc)), zc],
                         receptacle_wh=[w, r3(PH[msk].max() - max(PH[msk].min(), 0))],
                         face_x=face, plug_overmould_wh=plug,
                         note='wall cut-out must pass the plug overmould up to the receptacle face'))
usb_end = PL > 85.05
for name, s0, s1 in (('Gigabit Ethernet RJ45', -52.2, -36.0), ('USB 3.0 pair (blue)', -33.0, -17.8),
                     ('USB 2.0 pair', -14.9, 0.2)):
    msk = (PS >= s0) & (PS <= s1) & (PL > 66)   # jack bodies only (GPIO/PoE pins end at L 64)
    bxx = pi_box(msk & (PH > 0))
    face = r3(PI_Y(PL[msk & usb_end].max()))
    pi_ports.append(dict(name=name, faces='back (+y)', centre=[r3(np.mean(bxx['x'])), face, r3(np.mean(bxx['z']))],
                         body_box=bxx, face_y=face,
                         opening_wh=[r3(bxx['x'][1] - bxx['x'][0] + 1.0), r3(bxx['z'][1] - bxx['z'][0] + 1.0)]))
sd = PL < 0
sd_box = pi_box(sd)
soc = (PH > 1.0) & (PH < 2.4) & (PL > 21) & (PL < 37) & (PS > -39) & (PS < -23)
soc_box = pi_box(soc)

pi_holes = [dict(x=r3(PI_X(s)), y=r3(PI_Y(l)), drill=2.7, thread='M2.5', pad_dia=6.0)
            for l in (3.5, 61.5) for s in (1.62 - 52.5, 1.62 - 3.5)]
pi_top_env = pi_box(PH > 0)
pi_bot_env = pi_box(PH < -1.6)
usb_block = pi_box((PL > 66) & (PH > 3))

# ------------------------------------------------------------------ keep-outs
keepouts = [
    dict(name='HAT top-side component envelope (model)', x=[0, 140], y=[0, 136], z=[0, r3(max(
        p['model_bbox']['z'][1] for p in parts.values() if p['model_bbox'] and p['side'] == 'top'))]),
    dict(name='HAT top-side component envelope (as-built estimate, design to this)',
         x=[0, 140], y=[0, 136], z=[0, 20.0],
         note='Tallest fitted parts are estimated at 16-17 mm (C1/C18 electrolytics, C20/C60 MKT boxes). '
              'Lid underside >= 22.0 keeps >= 2 mm over a 20 mm part.'),
    dict(name='HAT solder side, lead protrusion (no Pi under it)', x=[0, 140], y=[0, 136], z=[-1.6 - 2.5, -1.6],
         note='THT leads are clipped to ~1.5-2.5 mm; the rework wires for U12 are on this side. '
              'Nothing may touch the copper side except the posts at the M3 holes.'),
    dict(name='J2 2x20 socket (bottom side)', **{k: v for k, v in parts['J2']['model_bbox'].items()}),
    dict(name='Raspberry Pi 4 (PCB + all parts incl. ports)', **pi_box(PH > -99)),
    dict(name='Pi underside parts (microSD socket/card, test pads)', **pi_bot_env),
    dict(name='Pi USB/Ethernet block (behind the HAT, rises above the HAT top)', **usb_block),
    dict(name='Pi PoE 4-pin header tips (under the HAT, 1.0 mm below its copper side)', **pi_box((PL > 60) & (PL < 65) & (PH > 3) & (PS < -40))),
    dict(name='Terminal-block wire gutter (cables enter from -x)', x=[-8.0, 0.0], y=[60.0, 132.0], z=[-1.6, 14.0],
         note='J20 / J3 / J60 wires enter horizontally from the left; keep 8 mm for the wire bend and ferrules.'),
    dict(name='Test-point header probe clearance (J5, J22, J62, J1)', x=[76.0, 84.0], y=[44.0, 117.0], z=[0, 20.0],
         note='Scope probe hooks need ~10 mm above the 8.5 mm pins: reached with the lid removed.'),
]

# ------------------------------------------------------------------ connectors needing access
def pc(ref): return parts[ref]['pad_centroid']
access = [
    dict(ref='J20', what='LINE IN L (2-pole 5.08 screw terminal)', centre=pc('J20'), faces='left (-x)', frequency='install'),
    dict(ref='J3', what='TONEARM GND (2-pole 5.08 screw terminal)', centre=pc('J3'), faces='left (-x)', frequency='install'),
    dict(ref='J60', what='LINE IN R (2-pole 5.08 screw terminal)', centre=pc('J60'), faces='left (-x)', frequency='install'),
    dict(ref='RV20', what='TRIM L (47k trimmer)', centre=pc('RV20'), faces='top (screwdriver)', frequency='rare, lid off OK'),
    dict(ref='RV60', what='TRIM R (47k trimmer)', centre=pc('RV60'), faces='top (screwdriver)', frequency='rare, lid off OK'),
    dict(ref='J1', what='CLK SEL jumper 1x3 (1-2 XTAL, 2-3 GPCLK; currently 2-3)', centre=pc('J1'), faces='top', frequency='rare, lid off OK'),
    dict(ref='J4', what='GND LIFT/BOND jumper 1x2', centre=pc('J4'), faces='top', frequency='rare, lid off OK'),
    dict(ref='J6', what='EEPROM WP jumper 1x2', centre=pc('J6'), faces='top', frequency='never'),
    dict(ref='J22', what='TP L 2x5 test header (odd = GND)', centre=pc('J22'), faces='top', frequency='bench, lid off'),
    dict(ref='J5', what='TP DIG 2x5 test header', centre=pc('J5'), faces='top', frequency='bench, lid off'),
    dict(ref='J62', what='TP R 2x5 test header', centre=pc('J62'), faces='top', frequency='bench, lid off'),
    dict(ref='SW1', what='SHUTDOWN / WAKE button (GPIO3)', centre=pc('SW1'), faces='top (press -z)', frequency='daily'),
    dict(ref='SW2', what='USER button (GPIO23)', centre=pc('SW2'), faces='top (press -z)', frequency='daily'),
]

out = dict(
    meta=dict(board='Vinyl ADC rev D (PCBWay, 4-layer, 1.6 mm, all THT) + Raspberry Pi 4B underneath',
              source_pcb=str(PCB.relative_to(REPO)), generated_by=str(pathlib.Path(__file__).relative_to(REPO)),
              units='mm, degrees',
              frame=dict(origin='board lower-left corner (front-left, LED edge at y=0)',
                         x='right', y='toward the back (Pi USB/Ethernet end)', z='up; 0 = top face of the HAT',
                         from_kicad_page='x = X - 51.06 ; y = 157.5 - Y',
                         note='rot_deg is KiCad orientation (CCW positive seen from the top, page frame).'),
              confidence='Positions, holes, outline: exact from the .kicad_pcb. Pi geometry: Pi 4B model + '
                         'render placement (matches the HAT hole pattern to 0.01 mm). Heights: KiCad 3D models '
                         'unless "as_built" says otherwise; as_built values are photo estimates -> MEASURE.'),
    board=dict(outline=dict(shape='rectangle', x=[0, W], y=[0, D], corner_radius=0.0),
               thickness=T, z_top=0.0, z_bottom=-T, copper_layers=4,
               zone_layers=zone_layers),
    holes=holes,
    stack=dict(z_hat_top=0.0, z_hat_bottom=-T, z_socket_bottom=r3(parts['J2']['model_bbox']['z'][0]),
               z_pi_pcb_top=Z_PI_TOP, z_pi_pcb_bottom=Z_PI_TOP - 1.6,
               z_pi_lowest_part=r3(PI_Z(PH.min())),
               hat_to_pi_standoff=dict(length=11.0, thread='M2.5', type='female-female (as BOM rev D)'),
               note='Pi PCB top is 11.0 below the HAT bottom: 8.5 mm socket + 2.5 mm header body.'),
    pi4=dict(pcb=dict(x=pi_pcb['x'], y=pi_pcb['y'], z=[Z_PI_TOP - 1.6, Z_PI_TOP], size=[56.0, 85.0], corner_radius=3.0,
                      orientation='short axis along x, flush with the HAT right edge; SD end at y=71, '
                                  'USB/Ethernet end at y=156 (20 mm past the HAT back edge)'),
             holes=pi_holes, gpio_header=dict(centre_x=r3(PI_X(1.62 - 52.5)), y=[r3(PI_Y(7.1)), r3(PI_Y(57.9))],
                                              pin1=parts['J2']['anchor']),
             ports=pi_ports,
             microsd=dict(box=sd_box, faces='front (-y), on the Pi underside, under the HAT',
                          note='Card tip at y~66.5 (socket mouth y~71), z -15.4..-14.6, card centre x~112. Not reachable from outside without a '
                               'floor slot; removing the Pi is the normal route.'),
             soc=dict(box=soc_box, note='BCM2711 heat source; sits under the HAT. Ventilate the floor below it.'),
             envelope_all=pi_box(PH > -99), envelope_top_side=pi_top_env, envelope_bottom_side=pi_bot_env,
             power='5 V 3 A via USB-C (right side wall). Pi 4 idles ~3 W, up to ~6 W.'),
    leds=dict(pitch=r3(pitch.mean()), pitch_min=r3(pitch.min()), pitch_max=r3(pitch.max()),
              row_y=leds[0]['centre'][1], items=leds,
              note='Centres are the optical axis (midpoint of the two pads), not the KiCad anchor (pad 1).'),
    switches=switches,
    access=access,
    keepouts=keepouts,
    parts=parts,
)
(HERE / 'board_mech.json').write_text(json.dumps(out, indent=1))

# ------------------------------------------------------------------ overlay on the top render
src = Image.open(TOP_PNG).convert('RGBA')
OX, OY = 160, 20       # where the 1800 x 1800 render sits on the wider canvas
im = Image.new('RGBA', (2300, 1880), (24, 25, 28, 255))
im.paste(src, (OX, OY))
S = 1800 / 176.0       # ortho_scale 0.176 m over 1800 px (render_rev_d.py 'top' shot)
def P(x, y): return (OX + 900 + (x - 70.0) * S, OY + 900 - (y - 77.0) * S)   # camera at board (70, 77)
ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
dr = ImageDraw.Draw(ov)
try:
    F = ImageFont.truetype('/usr/share/fonts/noto/NotoSansMono-Bold.ttf', 20)
    Fs = ImageFont.truetype('/usr/share/fonts/noto/NotoSansMono-Regular.ttf', 16)
except OSError:
    F = Fs = ImageFont.load_default()
CY, MG, YE, WH, OR, RD = (0, 230, 255, 255), (255, 60, 220, 255), (255, 235, 0, 255), (255, 255, 255, 255), (255, 150, 0, 255), (255, 50, 50, 255)


def rect(x0, x1, y0, y1, c, w=3):
    a, b_ = P(x0, y1), P(x1, y0)
    dr.rectangle([a, b_], outline=c, width=w)


def circ(x, y, r, c, w=3, fill=None):
    cx, cy = P(x, y)
    dr.ellipse([cx - r * S, cy - r * S, cx + r * S, cy + r * S], outline=c, width=w, fill=fill)


def cross(x, y, c, s=10):
    cx, cy = P(x, y)
    dr.line([cx - s, cy, cx + s, cy], fill=c, width=2); dr.line([cx, cy - s, cx, cy + s], fill=c, width=2)


def text(x, y, s, c=WH, f=None, anchor='la'):
    px, py = P(x, y)
    dr.text((px, py), s, fill=c, font=f or Fs, anchor=anchor, stroke_width=3, stroke_fill=(0, 0, 0, 255))


rect(0, W, 0, D, CY, 4)
rect(*pi_pcb['x'], *pi_pcb['y'], MG, 3)
text(pi_pcb['x'][0] + 1, 150, 'Pi 4 PCB  x %.1f..%.1f  y %.1f..%.1f' % (*pi_pcb['x'], *pi_pcb['y']), MG)
for h in holes:
    circ(h['x'], h['y'], h['drill'] / 2, YE, 3)
    cross(h['x'], h['y'], YE)
    lx = h['x'] + (3 if h['x'] < 100 else -3)
    text(lx, h['y'] + (-3.5 if h['y'] > 100 else 2.5), '%s %s (%.1f, %.1f)' % (h['ref'], h['thread'], h['x'], h['y']), YE,
         anchor='la' if h['x'] < 100 else 'ra')
for ph in pi_holes:
    circ(ph['x'], ph['y'], 3.0, MG, 2)
for l in leds:
    circ(*l['centre'], 2.5, OR, 3)
    cross(*l['centre'], OR, 6)
text(leds[0]['centre'][0] - 2.5, 13.5, 'LED row y=%.2f, pitch %.2f, x %.2f..%.2f' % (
    leds[0]['centre'][1], pitch.mean(), leds[0]['centre'][0], leds[-1]['centre'][0]), OR)
for l in leds:
    text(l['centre'][0], -2.0, '%.2f' % l['centre'][0], OR, anchor='ma')
for s_ in switches:
    rect(s_['centre'][0] - 3, s_['centre'][0] + 3, s_['centre'][1] - 3, s_['centre'][1] + 3, RD, 3)
    circ(*s_['centre'], 1.75, RD, 2)
    text(s_['centre'][0], 12.5 if s_['ref'] == 'SW1' else 15.5, '%s (%.2f, %.2f)' % (s_['ref'], *s_['centre']), RD, anchor='ma')
for a in access:
    if a['ref'] in ('J20', 'J3', 'J60', 'RV20', 'RV60', 'J1', 'J5', 'J22', 'J62', 'J4'):
        c = parts[a['ref']]['courtyard']
        rect(c['x'][0], c['x'][1], c['y'][0], c['y'][1], (90, 255, 120, 255), 2)
        text(c['x'][1] + 0.6, (c['y'][0] + c['y'][1]) / 2, '%s (%.1f,%.1f)' % (a['ref'], *a['centre']), (90, 255, 120, 255))
for port in pi_ports:
    x, y, z = port['centre']
    if port['faces'].startswith('right'):
        dr.line([P(140, y), P(146, y)], fill=MG, width=3)
        text(141, y + 1.2, '%s y=%.1f z=%.1f' % (port['name'].split(' ')[0], y, z), MG, anchor='la')
    else:
        dr.line([P(x, port['face_y']), P(x, port['face_y'] + 4)], fill=MG, width=3)
for nm, (x, y) in (('C1', pc('C1')), ('C18', pc('C18')), ('C20', pc('C20')), ('C60', pc('C60'))):
    circ(x, y, 1.0, (255, 255, 255, 255), 2)
# dimension lines
dr.line([P(0, -6), P(140, -6)], fill=CY, width=2); text(70, -6.6, '140.00', CY, F, 'ma')
dr.line([P(-6, 0), P(-6, 136)], fill=CY, width=2); text(-6.5, 68, '136.00', CY, F, 'rm')
text(1, 134.5, 'origin (0,0) = front-left corner; x right, y back', CY)
cross(0, 0, CY, 18)
Image.alpha_composite(im, ov).convert('RGB').save(HERE / 'top_overlay.png', optimize=True)
print('wrote board_mech.json, top_overlay.png')


# ------------------------------------------------------------------ side section (x-z, looking from the front)
# Board facts solid; the proposed shell levels from SPEC.md section 4 dashed.
SHELL = dict(x=[-11.4, 143.6], z_floor_bottom=-22.6, z_floor_top=-20.2, z_lid_under=22.0, z_lid_top=25.0, feet=3.2)
K = 9.0
cw, ch = int((SHELL['x'][1] - SHELL['x'][0] + 110) * K), int((SHELL['z_lid_top'] - SHELL['z_floor_bottom'] + SHELL['feet'] + 30) * K)
sec = Image.new('RGB', (cw, ch), (250, 250, 248))
g = ImageDraw.Draw(sec)
try:
    Fn = ImageFont.truetype('/usr/share/fonts/noto/NotoSansMono-Regular.ttf', 22)
except OSError:
    Fn = ImageFont.load_default()
def Q(x, z): return ((x - SHELL['x'][0] + 20) * K, (SHELL['z_lid_top'] + 12 - z) * K)
def box(x0, x1, z0, z1, fill=None, outline=(0, 0, 0), w=2):
    a, c = Q(x0, z1), Q(x1, z0)
    g.rectangle([a, c], fill=fill, outline=outline, width=w)
def dashed_h(z, x0, x1, col, lbl):
    x = x0
    while x < x1:
        g.line([Q(x, z), Q(min(x + 2, x1), z)], fill=col, width=2); x += 3.5
    g.text(Q(x1 + 1, z + 1.2), lbl, fill=col, font=Fn)
box(0, 140, -1.6, 0, fill=(40, 120, 60))                                           # HAT
box(*pi_pcb['x'], Z_PI_TOP - 1.6, Z_PI_TOP, fill=(30, 140, 80))                     # Pi PCB
box(84.96, 90.04, -10.2, -1.6, fill=(30, 30, 30))                                   # J2
for nm, (x, w_, h_) in {'C1': (96.75, 10, 17), 'C20/C60': (15.75, 19, 16), 'J20/J3/J60': (4.7, 8.1, 13.8),
                        'LED': (12.27, 5, 8.7), 'SW': (107.25, 6, 5.0)}.items():
    box(x - w_ / 2, x + w_ / 2, 0, h_, fill=(200, 200, 215))
    g.text(Q(x - w_ / 2, h_ + 2.6), '%s %.1f' % (nm, h_), fill=(0, 0, 0), font=Fn)
for port in pi_ports[:4]:
    pass
box(141.2 - 9, 141.2, -12.6, -9.44, fill=(170, 170, 170))                           # USB-C body (side)
g.text(Q(118, -7.5), 'USB-C c z=-11.0', fill=(0, 0, 0), font=Fn)
for z, lbl, col in ((SHELL['z_lid_top'], 'lid top +25.0 (3 mm acrylic)', (0, 90, 200)),
                    (SHELL['z_lid_under'], 'lid underside +22.0', (0, 90, 200)),
                    (0.0, 'HAT top 0.0 / bottom -1.6', (0, 120, 0)),
                    (-12.6, 'Pi PCB top -12.6 / bottom -14.2', (0, 120, 0)),
                    (-16.15, 'Pi lowest part -16.15', (0, 120, 0)),
                    (SHELL['z_floor_top'], 'floor top -20.2', (200, 60, 0)),
                    (SHELL['z_floor_bottom'], 'floor underside -22.6', (200, 60, 0)),
                    (SHELL['z_floor_bottom'] - SHELL['feet'], 'table -25.8 (feet 3.2) -> 50.8 overall', (200, 60, 0))):
    dashed_h(z, SHELL['x'][0], SHELL['x'][1], col, lbl)
for x in SHELL['x']:
    g.line([Q(x, SHELL['z_floor_bottom']), Q(x, SHELL['z_lid_top'])], fill=(200, 60, 0), width=3)
g.text(Q(SHELL['x'][0], SHELL['z_lid_top'] + 9), 'Section looking from the front (x right, z up). Solid = board facts, '
       'orange/blue = proposed shell.\n Heights of C1/C20/LED/SW are as-built ESTIMATES.', fill=(0, 0, 0), font=Fn)
sec.save(HERE / 'stack_section.png', optimize=True)
print('wrote stack_section.png')
