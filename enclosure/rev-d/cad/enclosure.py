"""Vinyl ADC rev D enclosure: parametric source (build123d).

    enclosure/rev-d/.venv/bin/python enclosure/rev-d/cad/enclosure.py [--set NAME=VALUE ...]

Concept "Faceplate + glass" (spec/AESTHETIC.md, concept 1), refined:

  tray       one PETG print: floor, left/right/back walls, three M3 HAT posts,
             four Pi bosses, port cut-outs, vent slots, lid-screw corbels.
  faceplate  one PETG print in the contrast colour: the 155 x 47.6 front face
             plus the top "deck" strip that covers the LED/switch row, an opaque
             comb of light cells (one per LED), two button guides and the two
             front lid-screw blocks. Printed face-down on textured PEI.
  pipe x8    natural PETG light pipes: the LEDs are seen as 3 mm frosted dots
             flush in the front face, one opaque cell each.
  button x2  accent-colour caps with a snap-retained stem, pressing straight
             down on SW1 / SW2; the cap bottoms out on the guide before the
             switch can be over-pressed.
  lid        3 mm cast acrylic (laser cut), flush in a rebate, 4 x M3 button heads.

Frame (spec/SPEC.md section 1): origin = HAT front-left corner, x right, y back,
z up, z = 0 on the HAT top face. All dimensions mm.

Every as-built height is a named parameter below, defaulting to the spec's
measured ESTIMATE. After measuring (README "measure first"), either edit the
values here, put them in cad/measured.json ({"LED_DOME_Z": 8.9, ...}), or pass
--set NAME=VALUE; check_fit.py reads the same values.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

# =============================================================================
# 1. AS-BUILT HEIGHTS -- ESTIMATES, MEASURE BEFORE PRINTING (SPEC section 7)
# =============================================================================
LED_DOME_Z = 8.7          # top of the 5 mm LED domes (est. 8.7 flush; KiCad model 11.6). Sets the light-pipe height.
SW_PLUNGER_Z = 5.0        # top of the SW1/SW2 plungers (est. 5.0; range 4.3-9.5). Sets the button stem length.
HAT_PI_STANDOFF = 11.0    # gap HAT bottom -> Pi PCB top (spec 11.0). Moves the Pi, its ports, bosses and floor.
DESIGN_ENVELOPE_Z = 20.0  # tallest thing on the HAT incl. margin (est. tallest part 17). Lid underside = this + LID_AIR.
LID_AIR = 2.0             # air between the envelope and the acrylic underside.
# Heights used only by the clearance check (check_fit.py); they do not move any geometry:
C1_C18_Z = 17.0           # 470 uF electrolytics (est. 17; range 12.5-20)
C5_C6_Z = 13.0            # 220 uF electrolytics (est. 13)
C20_C60_Z = 16.0          # MKT 373 boxes (est. 16), footprint envelope from board_mech.json
TERMINAL_BLOCK_Z = 13.8   # J20/J3/J60 (KiCad model 13.8; fitted blocks look ~10-11)
TRIMMER_Z = 12.0          # RV20/RV60 (body type unknown)
DIP_SOCKET_ADD = 4.5      # socketed DIPs: model height + this

# =============================================================================
# 2. OPTIONS
# =============================================================================
REAR_IO = 'rca'           # 'rca' = 2 panel RCA jacks + 4 mm ground post on the back; 'slot' = cable exit slot; 'none'
HDMI_OPENING = True       # micro-HDMI cut-out in the right wall (one slot for both)
AUDIO_OPENING = True      # 3.5 mm jack hole in the right wall
SD_SLOT = True            # floor slot under the microSD card tip (tweezers)
ENGRAVE_UNDERSIDE = True  # lid artwork mirrored, to be engraved on the underside (reads through the glass)
LEGENDS = True            # debossed LED / button / rear legends

# =============================================================================
# 3. SHELL AND FIT PARAMETERS
# =============================================================================
WALL = 3.0                # side and back walls
FRONT_T = 4.0             # faceplate front plate
DECK_T = 3.0              # faceplate top deck (= acrylic thickness, so the top is one plane)
FLOOR_T = 2.4
FEET_H = 3.2              # adhesive rubber feet; overall height = shell + this
LID_T = 3.0               # cast acrylic
FRAME = 1.2               # visible body frame around the glass (sides/back)
LID_GAP = 0.3             # acrylic to rebate, each side
LID_KERF = 0.18           # laser kerf, compensated in the DXF/SVG
GUTTER = 8.4              # left wall inner face to the HAT edge (terminal-block wires)
RIGHT_GAP = 0.6           # HAT right edge to the right wall inner face
BACK_INNER_Y = 159.6      # back wall inner face (Pi port faces at 158.85-159.36)
FRONT_GAP = 1.4           # HAT front edge to the faceplate inner face
DECK_BACK_Y = 15.0        # deck top runs y -5.4 .. here; the glass starts behind it
CORNER_R = 3.0            # the four vertical outer corners
CHAMFER_TOP = 0.6         # top outer edges (the frame around the glass is only 1.2 wide)
CHAMFER_FRONT = 1.0       # faceplate front-top and all bottom outer edges
SLIDE = 0.2               # sliding clearance per side (buttons in bores, parts against parts)
PORT_CLEAR = 0.8          # around connector / plug cut-outs, per side (0.4 hit the USB-C/HDMI overmoulds)

INSERT_PILOT_D = 4.2      # M3 heat-set insert pilot (enclosure/m3_insert_fit_coupon.stl)
INSERT_PILOT_DEPTH = 6.5
M3_CLEAR_D = 3.4
M25_CLEAR_D = 2.8
M3_HEAD_CB_D = 6.4        # counterbore for an M3 ISO 7380 head (5.7) under the floor
M3_HEAD_CB_DEPTH = 1.8
M25_HEAD_CB_D = 5.5       # SPEC 4: M2.5x10 from under the floor, 3 mm counterbore
M25_HEAD_CB_DEPTH = 3.0

HAT_POST_D = 8.0          # M3 posts under H1/H2/H3 (copper clearance >= 5.1 radius)
PI_BOSS_TOP_D = 6.0       # Pi pad is 6 mm
PI_BOSS_BASE_D = 8.5
PI_BOSS_H = 6.0           # Pi PCB bottom to floor top (4 mm air under the Pi's lowest part)

LID_SCREW_INSET = 5.7     # screw centres from the acrylic edges
LID_BOSS_DEPTH = 8.0      # insert boss below the lid seat
LID_BOSS_D = 9.0

# LEDs, light pipes
LED_X = [12.27, 21.77, 31.27, 40.77, 50.27, 59.77, 69.27, 78.77]
LED_Y = 6.0
LED_LABELS = ['CLIP L', 'CLIP R', '+5VA', '−5V', 'CLK', 'REC', 'BUSY', 'READY']
LED_COLOURS = ['red', 'red', 'green', 'yellow', 'green', 'red', 'yellow', 'green']
LED_PITCH = 9.5
PIPE_TIP_D = 3.0          # visible dot
PIPE_HOLE_D = 3.1         # front-plate bore (vertical in print, comes out round)
PIPE_BODY_D = 5.0
PIPE_TO_LED = 0.6         # pipe back face to the LED body
COMB_WALL = 1.2
COMB_BOTTOM_Z = 1.0       # cell walls stop this far above the HAT top (flange top is z 1.0)
COMB_BACK_Y = 9.2         # back wall of the cells (LED flange ends at y 8.9)
COMB_BACK_T = 1.0         # back wall thickness: its rear face (10.2) must clear R42 (body from y 10.5)
HAT_SCREW_HEAD_Z = 2.45   # M3 washer 0.8 + ISO 7380 head 1.65 on the HAT top at H2/H3; the comb clears it

# Buttons
SW = {'SW1': (107.25, 7.25), 'SW2': (121.25, 7.25)}
CAP_D = 10.0
CAP_T = 3.0
CAP_PROUD = 0.6           # cap top above the deck at rest
STOP_GAP = 0.6            # cap travel to its hard stop (switch actuates at 0.25)
STEM_D = 4.0
BORE_D = STEM_D + 2 * SLIDE
GUIDE_W = 8.0             # guide block width (x)
GUIDE_BOTTOM_Z = 10.0     # guide block underside
BARB_D = 5.0
BARB_FREE = 1.0           # how far the cap can lift before the barbs catch
STEM_SLIT = 1.2

FONT_LEGEND = '/usr/share/fonts/noto/NotoSans-Bold.ttf'
FONT_WORDMARK = '/usr/share/fonts/noto/NotoSans-Medium.ttf'
DEBOSS = 0.5

# Printer (Prusa MK4)
BED = (250.0, 210.0, 220.0)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'out'
BUILD = ROOT / 'build'


def _apply_overrides():
    """cad/measured.json, then --set NAME=VALUE on the command line."""
    g = globals()
    over = {}
    mj = HERE / 'measured.json'
    if mj.exists():
        over.update(json.loads(mj.read_text()))
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == '--set' and i + 1 < len(argv):
            k, v = argv[i + 1].split('=', 1)
            over[k] = v
    for k, v in over.items():
        if k not in g:
            raise SystemExit(f'unknown parameter {k}')
        cur = g[k]
        if isinstance(cur, bool):
            v = v if isinstance(v, bool) else str(v).lower() in ('1', 'true', 'yes')
        elif isinstance(cur, (int, float)):
            v = float(v)
        g[k] = v
    return over


OVERRIDES = _apply_overrides()

# =============================================================================
# 4. DERIVED LEVELS (do not edit; change the parameters above)
# =============================================================================
HAT_BOT_Z = -1.6
LID_UNDER_Z = DESIGN_ENVELOPE_Z + LID_AIR            # 22.0
TOP_Z = LID_UNDER_Z + LID_T                          # 25.0
PI_DZ = -(HAT_PI_STANDOFF - 11.0)                    # shift of every Pi z vs the spec numbers
PI_TOP_Z = HAT_BOT_Z - HAT_PI_STANDOFF               # -12.6
PI_BOT_Z = PI_TOP_Z - 1.6                            # -14.2
FLOOR_TOP_Z = PI_BOT_Z - PI_BOSS_H                   # -20.2
BOT_Z = FLOOR_TOP_Z - FLOOR_T                        # -22.6
OVERALL_H = TOP_Z - BOT_Z + FEET_H                   # 50.8

X0, X1 = -GUTTER - WALL, 140.0 + RIGHT_GAP + WALL    # -11.4, 143.6
XI0, XI1 = X0 + WALL, X1 - WALL                      # -8.4, 140.6
YF = -FRONT_GAP                                      # faceplate inner face, -1.4
Y0 = YF - FRONT_T                                    # front face, -5.4
YT0 = YF + SLIDE                                     # tray starts here, -1.2
YI1 = BACK_INNER_Y
Y1 = YI1 + WALL                                      # 162.6

# acrylic: rebate (frame inner edge) and the lid itself
REB = (X0 + FRAME, X1 - FRAME, DECK_BACK_Y, Y1 - FRAME)      # x0, x1, y0, y1
LID = (REB[0] + LID_GAP, REB[1] - LID_GAP, REB[2] + LID_GAP, REB[3] - LID_GAP)
LID_SCREWS = [(LID[0] + LID_SCREW_INSET, LID[2] + LID_SCREW_INSET),
              (LID[1] - LID_SCREW_INSET, LID[2] + LID_SCREW_INSET),
              (LID[0] + LID_SCREW_INSET, LID[3] - LID_SCREW_INSET),
              (LID[1] - LID_SCREW_INSET, LID[3] - LID_SCREW_INSET)]

PIPE_Z = LED_DOME_Z - 4.0                            # LED body side, works for flush and 3 mm-raised LEDs

HAT_POSTS = {'H2': (3.5, 3.5), 'H3': (136.5, 3.5), 'H1': (3.5, 132.5)}
PI_HOLES = [(87.52, 74.5), (136.52, 74.5), (87.52, 132.5), (136.52, 132.5)]
FACE_TABS_X = [30.0, 112.0]                          # faceplate -> floor screws
FEET = [(X0 + 20, Y0 + 20), (X1 - 20, Y0 + 20), (X0 + 20, Y1 - 20), (X1 - 20, Y1 - 20)]
REAR_IO_Z = -4.0
REAR_RCA = [('L', 34.0), ('R', 52.0)]
REAR_GND_X = 14.0
RCA_HOLE_D = 9.7          # 9.5 mm panel hole + 0.2 horizontal-hole shrink
GND_HOLE_D = 6.2

# Pi ports (spec frame, nominal 11 mm standoff; PI_DZ applied)
P_USBC = (82.2, -11.02)
P_HDMI = [(97.0, -11.18), (110.5, -11.18)]
P_AUDIO = (125.0, -9.6)
P_ETH_X = (86.21, 102.365); P_ETH_Z = (-12.6, 1.05)
P_USB3_X = (105.515, 120.515); P_USB3_Z = (-12.6, 3.74)
P_USB2_X = (123.565, 138.465); P_USB2_Z = (-12.6, 3.007)

# =============================================================================
# 5. GEOMETRY
# =============================================================================
from build123d import (Align, Axis, Box, Circle, Color, Compound, Cone, Cylinder,
                       Location, Mesher, Plane, Polygon, Pos, Rectangle,
                       RectangleRounded, Rot, SlotOverall, Sketch, Text,
                       export_step, export_stl, extrude, fillet, Unit)


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def cyl(x, y, z0, z1, d):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(d / 2, z1 - z0)


def cone(x, y, z0, z1, d0, d1):
    return Pos(x, y, (z0 + z1) / 2) * Cone(d0 / 2, d1 / 2, z1 - z0)


# Planes whose local (u, v) are world axes; extrude(plane * sketch, amount) goes along z_dir.
def plane_x(x):          # u = +y, v = +z, normal +x
    return Plane(origin=(x, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))


def plane_front(y):      # u = +x, v = +z, normal -y (reads from the front)
    return Plane(origin=(0, y, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))


def plane_back(y):       # u = -x, v = +z, normal +y (reads from behind)
    return Plane(origin=(0, y, 0), x_dir=(-1, 0, 0), z_dir=(0, 1, 0))


def plane_top(z):        # u = +x, v = +y, normal +z
    return Plane(origin=(0, 0, z), x_dir=(1, 0, 0), z_dir=(0, 0, 1))


def ext(plane, sk, amount):
    """Extrude a sketch placed on 'plane' along the plane normal (whatever the face winding)."""
    return extrude(plane * sk, amount=amount, dir=plane.z_dir)


def prism_x(sk, x0, x1):
    return ext(plane_x(x0), sk, x1 - x0)


def prism_y(sk_xz, y0, y1):
    """Sketch in (x, z) coordinates, extruded from y0 to y1."""
    return ext(plane_front(y1), sk_xz, y1 - y0)


def prism_z(sk, z0, z1):
    return ext(plane_top(z0), sk, z1 - z0)


def rrect(cx, cy, w, h, r):
    return Pos(cx, cy) * RectangleRounded(w, h, min(r, w / 2 - 0.01, h / 2 - 0.01))


def rect_lr(x0, x1, y0, y1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2) * Rectangle(x1 - x0, y1 - y0)


def plan_rect(x0, x1, y0, y1, r_front, r_back):
    """Rectangle with separate radii on the y0 (front) and y1 (back) corners."""
    s = rect_lr(x0, x1, y0, y1)
    if r_front:
        s = fillet(s.vertices().filter_by_position(Axis.Y, y0 - 0.01, y0 + 0.01), r_front)
    if r_back:
        s = fillet(s.vertices().filter_by_position(Axis.Y, y1 - 0.01, y1 + 0.01), r_back)
    return s


def chamfered_rect(u0, u1, v0, v1, c_bottom, c_top):
    pts = [(u0 + c_bottom, v0), (u1 - c_bottom, v0), (u1, v0 + c_bottom), (u1, v1 - c_top),
           (u1 - c_top, v1), (u0 + c_top, v1), (u0, v1 - c_top), (u0, v0 + c_bottom)]
    return Polygon(*pts, align=None)


def teardrop(cx, cy, d, up=(0, 1)):
    """Circle plus a 45 degree roof pointing along 'up' (sketch coords): prints horizontal without support."""
    r = d / 2
    ux, uy = up
    tip = (cx + ux * r * math.sqrt(2), cy + uy * r * math.sqrt(2))
    a = (cx + (ux * math.cos(math.radians(45)) - uy * math.sin(math.radians(45))) * r,
         cy + (ux * math.sin(math.radians(45)) + uy * math.cos(math.radians(45))) * r)
    b = (cx + (ux * math.cos(math.radians(-45)) - uy * math.sin(math.radians(-45))) * r,
         cy + (ux * math.sin(math.radians(-45)) + uy * math.cos(math.radians(-45))) * r)
    return Pos(cx, cy) * Circle(r) + Polygon((cx, cy), a, tip, b, align=None)


def text_sketch(s, cap_h, font=FONT_LEGEND, tracking=0.12, align='center'):
    """Text with letter tracking (em fraction); (0,0) at the cap-height centre of the line."""
    fs = cap_h / 0.734
    shapes, x = [], 0.0
    for ch in s:
        if ch == ' ':
            x += fs * 0.30
            continue
        t = Text(ch, fs, font_path=font, align=(Align.MIN, Align.MIN))
        bb = t.bounding_box()
        shapes.append(Pos(x - bb.min.X, 0) * t)
        x += bb.size.X + fs * tracking
    x -= fs * tracking
    sk = Sketch() + shapes
    dx = {'center': -x / 2, 'left': 0.0, 'right': -x}[align]
    return Pos(dx, -cap_h / 2) * sk, x


def power_symbol(r=1.7, w=0.55):
    ring = Circle(r) - Circle(r - w)
    ring = ring - Pos(0, r * 0.75) * Rectangle(r * 1.05, r * 1.6)
    bar = Pos(0, r * 0.45) * RectangleRounded(w, r * 1.25, w / 2 - 0.01)
    return ring + bar


# -----------------------------------------------------------------------------
def outer_solid(x0, x1, y0, y1, z0, z1, r_front, r_back, c_bot_front, c_top_front, c_bot_back, c_top_back,
                c_side_bot, c_side_top):
    """Rounded-corner block with chamfered horizontal edges, as the intersection of three prisms."""
    plan = prism_z(plan_rect(x0, x1, y0, y1, r_front, r_back), z0, z1)
    # side profile (y, z), extruded along x
    pts = [(y0 + c_bot_front, z0), (y1 - c_bot_back, z0), (y1, z0 + c_bot_back), (y1, z1 - c_top_back),
           (y1 - c_top_back, z1), (y0 + c_top_front, z1), (y0, z1 - c_top_front), (y0, z0 + c_bot_front)]
    side = prism_x(Polygon(*pts, align=None), x0 - 1, x1 + 1)
    front = prism_y(chamfered_rect(x0, x1, z0, z1, c_side_bot, c_side_top), y0 - 1, y1 + 1)
    return plan & side & front


# -----------------------------------------------------------------------------
def tray():
    t = outer_solid(X0, X1, YT0, Y1, BOT_Z, TOP_Z, 0, CORNER_R,
                    0, 0, CHAMFER_FRONT, CHAMFER_TOP, CHAMFER_FRONT, CHAMFER_TOP)
    # cavity, open at the front (the faceplate closes it)
    t -= prism_z(plan_rect(XI0, XI1, YT0 - 5, YI1, 0, 1.0), FLOOR_TOP_Z, TOP_Z + 1)
    # walls under the deck stop at the deck underside
    t -= box(X0 - 1, X1 + 1, YT0 - 1, DECK_BACK_Y, LID_UNDER_Z, TOP_Z + 1)
    # lid rebate
    t -= prism_z(plan_rect(REB[0], REB[1], REB[2] - 1, REB[3], 0, 2.0), LID_UNDER_Z, TOP_Z + 1)

    # --- HAT posts (M3 inserts on top) ---
    for ref, (x, y) in HAT_POSTS.items():
        t += cyl(x, y, FLOOR_TOP_Z - 0.1, HAT_BOT_Z, HAT_POST_D)
        t += cone(x, y, FLOOR_TOP_Z - 0.1, FLOOR_TOP_Z + 2.0, HAT_POST_D + 4, HAT_POST_D) & box(XI0, XI1, YT0, YI1, BOT_Z, TOP_Z)
    # --- Pi bosses ---
    for x, y in PI_HOLES:
        t += cone(x, y, FLOOR_TOP_Z - 0.1, PI_BOT_Z, PI_BOSS_BASE_D, PI_BOSS_TOP_D)
    # --- back lid-screw bosses on 45 degree corbels (clear of the USB jacks) ---
    for (sx, sy), (cx, cy) in zip(LID_SCREWS[2:], [(XI0, YI1), (XI1, YI1)]):
        zb = LID_UNDER_Z - LID_BOSS_DEPTH
        boss = cyl(sx, sy, zb, LID_UNDER_Z, LID_BOSS_D)
        r = math.hypot(sx - cx, sy - cy) + LID_BOSS_D / 2 + 0.5
        corb = cone(cx, cy, zb - r, zb, 0.01, 2 * r)
        corb &= box(XI0 - 0.01, XI1 + 0.01, YT0, YI1 + 0.01, zb - r, zb)
        t += boss + corb

    # --- faceplate tabs land on the floor: screw from below ---
    for x in FACE_TABS_X:
        t -= cyl(x, YF + 5.0, BOT_Z - 1, FLOOR_TOP_Z + 1, M3_CLEAR_D)
        t -= cyl(x, YF + 5.0, BOT_Z - 1, BOT_Z + M3_HEAD_CB_DEPTH, M3_HEAD_CB_D)
    # --- holes: HAT post inserts, Pi screws, lid inserts ---
    for x, y in HAT_POSTS.values():
        t -= cyl(x, y, HAT_BOT_Z - INSERT_PILOT_DEPTH, HAT_BOT_Z + 1, INSERT_PILOT_D)
    for x, y in PI_HOLES:
        t -= cyl(x, y, BOT_Z - 1, PI_BOT_Z + 1, M25_CLEAR_D)
        t -= cyl(x, y, BOT_Z - 1, BOT_Z + M25_HEAD_CB_DEPTH, M25_HEAD_CB_D)
    for x, y in LID_SCREWS[2:]:
        t -= cyl(x, y, LID_UNDER_Z - INSERT_PILOT_DEPTH, LID_UNDER_Z + 1, INSERT_PILOT_D)

    # --- right wall: Pi ports (cut for the plug overmoulds) ---
    def right_cut(sk):
        return prism_x(sk, XI1 - 1.5, X1 + 1)
    z = P_USBC[1] + PI_DZ
    t -= right_cut(rrect(P_USBC[0], z, 12.5 + 2 * PORT_CLEAR, 7.0 + 2 * PORT_CLEAR, 2.0))
    if HDMI_OPENING:
        ya = P_HDMI[0][0] - 11.5 / 2 - PORT_CLEAR
        yb = P_HDMI[1][0] + 11.5 / 2 + PORT_CLEAR
        z = P_HDMI[0][1] + PI_DZ
        t -= right_cut(rrect((ya + yb) / 2, z, yb - ya, 7.5 + 2 * PORT_CLEAR, 2.0))
    if AUDIO_OPENING:
        t -= right_cut(Pos(P_AUDIO[0], P_AUDIO[1] + PI_DZ) * Circle(4.6))

    # --- back wall: Ethernet, USB 3, USB 2 ---
    def back_cut(x0, x1, z0, z1, r=1.5):
        return prism_y(rrect((x0 + x1) / 2, (z0 + z1) / 2, x1 - x0, z1 - z0, r), YI1 - 1, Y1 + 1)
    zb = P_ETH_Z[0] + PI_DZ - 0.6
    t -= back_cut(P_ETH_X[0] - PORT_CLEAR, P_ETH_X[1] + PORT_CLEAR, zb, P_ETH_Z[1] + PI_DZ + 0.6)
    usb_top = max(P_USB3_Z[1], P_USB2_Z[1]) + PI_DZ + 1.0      # room for the upper plug's overmould
    # the lower plug's overmould (8 mm tall, centred 12.3 below the jack top) hangs below the Pi top
    usb_bot = min(P_USB3_Z[1], P_USB2_Z[1]) + PI_DZ - 12.3 - 4.0 - PORT_CLEAR
    rib = (P_USB3_X[1] + P_USB2_X[0]) / 2
    t -= back_cut(P_USB3_X[0] - PORT_CLEAR - 0.5, rib - 0.8, usb_bot, usb_top, r=1.0)
    t -= back_cut(rib + 0.8, min(P_USB2_X[1] + PORT_CLEAR + 0.7, XI1 - 1.0), usb_bot, usb_top, r=1.0)

    # --- rear panel: RCA L/R + ground post, or a cable slot ---
    if REAR_IO == 'rca':
        for _, x in REAR_RCA:
            t -= prism_y(Pos(x, REAR_IO_Z) * Circle(RCA_HOLE_D / 2), YI1 - 1, Y1 + 1)
        t -= prism_y(Pos(REAR_GND_X, REAR_IO_Z) * Circle(GND_HOLE_D / 2), YI1 - 1, Y1 + 1)
    elif REAR_IO == 'slot':
        t -= prism_y(Pos(30, REAR_IO_Z) * SlotOverall(16, 7), YI1 - 1, Y1 + 1)

    # --- vents: floor field under the Pi, side grilles, back grille ---
    for x in [95.0 + 4.0 * i for i in range(9)]:
        for ya, yb in ((81.0, 102.0), (106.0, 127.0)):
            t -= prism_z(Pos(x, (ya + yb) / 2) * Rot(0, 0, 90) * SlotOverall(yb - ya, 2.0), BOT_Z - 1, FLOOR_TOP_Z + 1)
    if SD_SLOT:
        t -= prism_z(rrect(112.0, 64.5, 16.0, 9.0, 3.0), BOT_Z - 1, FLOOR_TOP_Z + 1)
    for i in range(6):
        y = 134.0 + 4.0 * i
        slot = Pos(y, -11.0) * Rot(0, 0, 90) * SlotOverall(12.0, 2.0)
        t -= prism_x(slot, X0 - 1, XI0 + 1)
        t -= prism_x(slot, XI1 - 1, X1 + 1)
    for i in range(5):
        x = 64.0 + 4.0 * i
        t -= prism_y(Pos(x, -11.0) * Rot(0, 0, 90) * SlotOverall(12.0, 2.0), YI1 - 1, Y1 + 1)

    # --- the line: a fine groove round the sides and back, just under the glass plane ---
    gz = LID_UNDER_Z - 1.0
    ring = prism_z(plan_rect(X0 - 1, X1 + 1, YT0 - 1, Y1 + 1, 0, 0), gz - 0.3, gz + 0.3)
    ring -= prism_z(plan_rect(X0 + 0.4, X1 - 0.4, YT0 - 2, Y1 - 0.4, 0, CORNER_R - 0.4), gz - 0.4, gz + 0.4)
    t -= ring

    # --- feet recesses ---
    for x, y in FEET:
        t -= cyl(x, y, BOT_Z - 1, BOT_Z + 0.5, 12.6)

    # --- rear legends ---
    if LEGENDS and REAR_IO == 'rca':
        for name, x in REAR_RCA + [('GND', REAR_GND_X)]:
            sk, _ = text_sketch(name, 2.4)
            t -= ext(plane_back(Y1), (Pos(-x, REAR_IO_Z + 9.0) * sk), -DEBOSS)
        sk, _ = text_sketch('LINE IN', 1.8, tracking=0.2)
        t -= ext(plane_back(Y1), (Pos(-sum(x for _, x in REAR_RCA) / 2, REAR_IO_Z - 9.0) * sk), -DEBOSS)
    return t


# -----------------------------------------------------------------------------
def faceplate():
    # front plate + deck, as one outer solid then carved
    plate = outer_solid(X0, X1, Y0, YF, BOT_Z, TOP_Z, CORNER_R, 0,
                        CHAMFER_FRONT, CHAMFER_FRONT, 0, 0, CHAMFER_FRONT, CHAMFER_TOP)
    deck = outer_solid(X0, X1, Y0, DECK_BACK_Y - SLIDE, LID_UNDER_Z, TOP_Z, CORNER_R, 0,
                       0, CHAMFER_FRONT, 0, 0, 0, CHAMFER_TOP)
    f = plate + deck

    # under-deck structures, all built so they print face-down without support
    # lid ledge behind the deck: 45 degree front face
    ledge_prof = Polygon((12.5, LID_UNDER_Z), (DECK_BACK_Y + 3.5, LID_UNDER_Z),
                         (DECK_BACK_Y + 3.5, LID_UNDER_Z - 2.0), (14.5, LID_UNDER_Z - 2.0), align=None)
    f += prism_x(ledge_prof, XI0 + SLIDE, XI1 - SLIDE)
    # front lid-screw blocks (insert from the top), 45 degree underside towards the front
    for sx, sy in LID_SCREWS[:2]:
        zb = LID_UNDER_Z - LID_BOSS_DEPTH
        y_end = sy + 4.0
        prof = Polygon((sy - 11.0, LID_UNDER_Z), (y_end, LID_UNDER_Z), (y_end, zb),
                       (sy - 11.0 + (LID_UNDER_Z - zb), zb), align=None)
        bx0 = max(sx - 4.0, XI0 + SLIDE)
        bx1 = min(sx + 4.0, XI1 - SLIDE)
        f += prism_x(prof, bx0, bx1)
        f -= cyl(sx, sy, LID_UNDER_Z - INSERT_PILOT_DEPTH, LID_UNDER_Z + 1, INSERT_PILOT_D)
    # light cells: walls between LEDs, back wall
    xs = [LED_X[0] - LED_PITCH / 2 + LED_PITCH * i for i in range(len(LED_X) + 1)]
    for x in xs:
        f += box(x - COMB_WALL / 2, x + COMB_WALL / 2, YF - 0.01, COMB_BACK_Y + COMB_BACK_T,
                 COMB_BOTTOM_Z, LID_UNDER_Z + 0.01)
    f += box(xs[0] - COMB_WALL / 2, xs[-1] + COMB_WALL / 2, COMB_BACK_Y, COMB_BACK_Y + COMB_BACK_T,
             COMB_BOTTOM_Z, LID_UNDER_Z + 0.01)
    # notch the last cell wall over R56's lead bend (it touched at z 1.1)
    f -= box(xs[-1] - COMB_WALL / 2 - 0.01, xs[-1] + COMB_WALL / 2 + 0.01, 4.75 - 0.3, 7.25 + 0.3,
             COMB_BOTTOM_Z - 1, 2.5 + 0.3)
    # pockets over the front HAT screw heads (the first comb wall would sit on H2's washer)
    for x, y in HAT_POSTS.values():
        if y < COMB_BACK_Y:
            f -= cyl(x, y, COMB_BOTTOM_Z - 1, HAT_SCREW_HEAD_Z + 0.4, 7.0 + 2 * 0.4)
    # button guides
    for x, y in SW.values():
        f += box(x - GUIDE_W / 2, x + GUIDE_W / 2, YF - 0.01, y + BORE_D / 2 + 1.8,
                 GUIDE_BOTTOM_Z, LID_UNDER_Z + 0.01)
    # floor tabs with inserts from below
    for x in FACE_TABS_X:
        f += box(x - 6, x + 6, YF - 0.01, YF + 10.0, FLOOR_TOP_Z, FLOOR_TOP_Z + 8.0)
        # pilot as a teardrop pointing +y (up in the print)
        f -= prism_z(teardrop(x, YF + 5.0, INSERT_PILOT_D, up=(0, 1)), FLOOR_TOP_Z - 1, FLOOR_TOP_Z + 7.0)

    # cut: button counterbores + guide bores (teardrop, pointing +y)
    for x, y in SW.values():
        f -= cyl(x, y, LID_UNDER_Z, TOP_Z + 1, CAP_D + 2 * 0.3)
        f -= prism_z(teardrop(x, y, BORE_D, up=(0, 1)), GUIDE_BOTTOM_Z - 1, LID_UNDER_Z + 0.5)
    # cut: light-pipe bores
    for x in LED_X:
        f -= prism_y(Pos(x, PIPE_Z) * Circle(PIPE_HOLE_D / 2), Y0 - 1, YF + 0.5)

    # legends: LED names under the dots, wordmark at the right, button names on the deck
    if LEGENDS:
        for x, name in zip(LED_X, LED_LABELS):
            sk, _ = text_sketch(name, 1.7, tracking=0.08)
            f -= ext(plane_front(Y0), (Pos(x, PIPE_Z - 4.4) * sk), -DEBOSS)
        sk, w = text_sketch('VINYL ADC', 3.4, font=FONT_WORDMARK, tracking=0.32, align='right')
        f -= ext(plane_front(Y0), (Pos(X1 - 23.7, PIPE_Z) * sk), -DEBOSS)
        for (x, y), name in zip(SW.values(), ['POWER', 'REC']):
            sk, _ = text_sketch(name, 1.7, tracking=0.12)
            f -= ext(plane_top(TOP_Z), (Pos(x, y - CAP_D / 2 - 2.6) * sk), -DEBOSS)
    return f


# -----------------------------------------------------------------------------
def light_pipe(x):
    """Natural PETG pipe; front tip flush with the face, body reaches to PIPE_TO_LED from the LED."""
    y_back = LED_Y - 2.5 - PIPE_TO_LED
    tip = prism_y(Pos(x, PIPE_Z) * Circle(PIPE_TIP_D / 2), Y0, YF + 0.01)
    body = prism_y(Pos(x, PIPE_Z) * Circle(PIPE_BODY_D / 2), YF, y_back)
    return tip + body


def button(name):
    x, y = SW[name]
    cap_top = TOP_Z + CAP_PROUD
    cap_bot = cap_top - CAP_T
    tip_z = SW_PLUNGER_Z
    b = cyl(x, y, cap_bot, cap_top, CAP_D)
    # 0.5 chamfer round the cap top
    b -= cyl(x, y, cap_top - 0.5, cap_top + 1, CAP_D + 2) - cone(x, y, cap_top - 0.5, cap_top + 0.001, CAP_D, CAP_D - 1.0)
    b += cyl(x, y, tip_z, cap_bot + 0.01, STEM_D)
    # snap barbs just below the guide, ramped towards the tip
    zc = GUIDE_BOTTOM_Z - BARB_FREE
    b += cone(x, y, zc - 1.6, zc, STEM_D, BARB_D)
    # slit so the barbs can pass the bore
    b -= box(x - 3, x + 3, y - STEM_SLIT / 2, y + STEM_SLIT / 2, tip_z - 1, zc + 5.0)
    # symbol on the cap
    sym = power_symbol() if name == 'SW1' else Circle(1.5)
    b -= ext(plane_top(cap_top), (Pos(x, y) * sym), -0.4)
    return b


# -----------------------------------------------------------------------------
def lid_shapes():
    """2D cut + engrave artwork for the acrylic, in the world x/y frame (seen from above)."""
    w, h = LID[1] - LID[0], LID[3] - LID[2]
    cx, cy = (LID[0] + LID[1]) / 2, (LID[2] + LID[3]) / 2
    k = LID_KERF / 2
    outline = rrect(cx, cy, w + 2 * k, h + 2 * k, 2.0 - LID_GAP + k)
    holes = [Pos(x, y) * Circle(M3_CLEAR_D / 2 - k) for x, y in LID_SCREWS]
    eng = []
    # wordmark over the empty back-left bay
    sk, _ = text_sketch('VINYL ADC', 5.0, font=FONT_WORDMARK, tracking=0.32, align='left')
    eng.append(Pos(4.0, 151.0) * sk)
    sk, _ = text_sketch('REV D  ·  RASPBERRY PI 4 HAT  ·  MADSRUDOLPH.DEV', 1.8, tracking=0.18, align='left')
    eng.append(Pos(4.2, 144.5) * sk)
    # corner marks at the HAT corners (0.3 mm lines)
    for bx, by, sx, sy in ((0, 0, 1, 1), (140, 0, -1, 1), (0, 136, 1, -1), (140, 136, -1, -1)):
        if by == 0:
            continue  # front corners sit under the deck
        eng.append(rect_lr(min(bx, bx + 4 * sx), max(bx, bx + 4 * sx), by - 0.15, by + 0.15))
        eng.append(rect_lr(bx - 0.15, bx + 0.15, min(by, by + 4 * sy), max(by, by + 4 * sy)))
    return outline, holes, eng


def export_lid():
    from build123d import ExportDXF, ExportSVG
    from build123d.exporters import ColorIndex
    outline, holes, eng = lid_shapes()
    mirror_x = (LID[0] + LID[1]) if ENGRAVE_UNDERSIDE else None

    def place(s):
        # move to a sheet frame with the lid's lower-left corner at (5, 5)
        s = Pos(-LID[0] + 5, -LID[2] + 5) * s
        return s

    def mir(s):
        if mirror_x is None:
            return s
        return s.mirror(Plane(origin=((LID[0] + LID[1]) / 2, 0, 0), z_dir=(1, 0, 0)))

    cut = [place(outline.face().outer_wire())] + [place(hh.face().outer_wire()) for hh in holes]
    engr = [place(mir(e)) for e in eng]
    dxf = ExportDXF(unit=Unit.MM)
    dxf.add_layer('CUT', color=ColorIndex.RED)
    dxf.add_layer('ENGRAVE', color=ColorIndex.BLUE)
    for c in cut:
        dxf.add_shape(c, layer='CUT')
    for e in engr:
        for fc in e.faces():
            dxf.add_shape(fc.wires(), layer='ENGRAVE')
    dxf.write(OUT / 'lid.dxf')
    svg = ExportSVG(unit=Unit.MM, margin=0, line_weight=0.05)
    svg.add_layer('CUT', line_color=(255, 0, 0), line_weight=0.05)
    svg.add_layer('ENGRAVE', fill_color=(0, 0, 255), line_color=(0, 0, 255), line_weight=0.0)
    for c in cut:
        svg.add_shape(c, layer='CUT')
    for e in engr:
        for fc in e.faces():
            svg.add_shape(fc, layer='ENGRAVE')
    svg.write(OUT / 'lid.svg')


def lid_solid():
    outline, holes, _ = lid_shapes()
    s = outline
    for hh in holes:
        s = s - hh
    return prism_z(s, LID_UNDER_Z, TOP_Z)


# =============================================================================
# 6. PRINT ORIENTATIONS AND EXPORT
# =============================================================================
def to_bed(shape, how):
    if how == 'face_down':        # front face (normal -y) on the bed
        s = Rot(90, 0, 0) * shape
    elif how == 'cap_down':       # +z face on the bed
        s = Rot(180, 0, 0) * shape
    else:
        s = shape
    bb = s.bounding_box()
    return Pos(-bb.min.X - bb.size.X / 2, -bb.min.Y - bb.size.Y / 2, -bb.min.Z) * s


def build_all():
    parts = {}
    parts['tray'] = (tray(), 'floor_down', 'matte black PETG', (0.03, 0.03, 0.035))
    parts['faceplate'] = (faceplate(), 'face_down', 'silver/aluminium PETG', (0.70, 0.71, 0.72))
    for i, x in enumerate(LED_X):
        parts[f'pipe_{i + 1}'] = (light_pipe(x), 'face_down', 'natural PETG', (0.9, 0.9, 0.85))
    parts['button_sw1'] = (button('SW1'), 'cap_down', 'accent PETG (copper/orange)', (0.85, 0.38, 0.10))
    parts['button_sw2'] = (button('SW2'), 'cap_down', 'accent PETG (copper/orange)', (0.85, 0.38, 0.10))
    return parts


def main():
    OUT.mkdir(exist_ok=True)
    (BUILD / 'asm').mkdir(parents=True, exist_ok=True)
    parts = build_all()
    report = {'overrides': OVERRIDES, 'levels': dict(TOP_Z=TOP_Z, LID_UNDER_Z=LID_UNDER_Z, PI_TOP_Z=PI_TOP_Z,
              FLOOR_TOP_Z=FLOOR_TOP_Z, BOT_Z=BOT_Z, OVERALL_H=OVERALL_H, PIPE_Z=PIPE_Z),
              'outer': dict(x=[X0, X1], y=[Y0, Y1], w=X1 - X0, d=Y1 - Y0), 'lid': LID, 'parts': {}}
    asm_children = []
    for name, (shape, how, mat, rgb) in parts.items():
        if not shape.is_valid:
            print('WARNING: invalid solid', name)
        export_stl(shape, BUILD / 'asm' / f'{name}.stl', tolerance=0.02, angular_tolerance=0.15)
        bed = to_bed(shape, how)
        bb = bed.bounding_box()
        fits = bb.size.X <= BED[0] and bb.size.Y <= BED[1] and bb.size.Z <= BED[2]
        report['parts'][name] = dict(orientation=how, material=mat, volume_cm3=round(shape.volume / 1000, 2),
                                     bed_size=[round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)],
                                     fits_bed=fits)
        if name.startswith('pipe_') and name != 'pipe_1':
            continue
        stem = 'light_pipe' if name.startswith('pipe_') else name
        export_stl(bed, OUT / f'{stem}.stl', tolerance=0.01, angular_tolerance=0.1)
        m = Mesher(unit=Unit.MM)
        m.add_shape(bed, linear_deflection=0.01, angular_deflection=0.1)
        m.add_meta_data('vinyl-adc', 'part', stem, 'xs:string', False)
        m.write(str(OUT / f'{stem}.3mf'))
        c = shape.moved(Location())
        c.label = name
        c.color = Color(*rgb)
        asm_children.append(c)
    lid = lid_solid()
    lid.label = 'lid_acrylic'
    lid.color = Color(0.85, 0.92, 0.95, 0.3)
    export_stl(lid, BUILD / 'asm' / 'lid.stl', tolerance=0.02, angular_tolerance=0.15)
    asm_children.append(lid)
    asm = Compound(label='vinyl_adc_rev_d_enclosure', children=asm_children)
    export_step(asm, OUT / 'enclosure.step')
    export_lid()
    # legend inlay for multi-material printing would go here (not exported by default)
    (BUILD / 'build_report.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
