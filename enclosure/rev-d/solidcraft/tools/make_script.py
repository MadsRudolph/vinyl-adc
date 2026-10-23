"""Write the SolidCraft command script that builds the rev D enclosure assembly.

    python3 enclosure/rev-d/solidcraft/tools/make_script.py          # writes ../build_assembly.json
    tools/capped -m 3G solidcraft-cli run enclosure/rev-d/solidcraft/build_assembly.json \
        --save enclosure/rev-d/solidcraft/vinyl_adc_rev_d_assembly.solidcraft

Plain Python, no geometry: it only writes JSON. Every number below is copied from
cad/enclosure.py (section 3/4) or spec/SPEC.md and says where it came from. If the
enclosure parameters change, rerun enclosure.py, then this, then solidcraft-cli.

Frame: the board frame of SPEC section 1 (origin HAT front-left corner, z = 0 on
the HAT top face). enclosure.step is already in that frame, so its parts need no
move. The HAT STEP from kicad-cli has its board bottom at z = 0 (move -1.6), and
the Pi 4B STEP comes in its own frame (turned and moved, see PI_* below).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SC = HERE.parent                                  # enclosure/rev-d/solidcraft
REV = SC.parent                                   # enclosure/rev-d
REPO = REV.parents[1]

ENCLOSURE_STEP = REV / 'out' / 'enclosure.step'
LID_DXF = SC / 'parts' / 'lid_cut.dxf'            # tools/lid_cut_dxf.py: out/lid.dxf, CUT layer only
HAT_STEP = SC / 'parts' / 'hat_rev_d.step'        # tools/export_hat_step.sh
PI_STEP = REPO / 'hardware/kicad/rev_d/render/build/pi4/pi4b.step'   # render/export_model.sh downloads it

# --- from enclosure.py --------------------------------------------------------
LID_T = 3.0                    # LID_T, cast acrylic
LID_UNDER_Z = 22.0             # LID_UNDER_Z = DESIGN_ENVELOPE_Z + LID_AIR
LID = (-9.9, 142.1, 15.3, 161.1)   # LID (x0, x1, y0, y1), also build/build_report.json
LED_PITCH = 9.5                # LED_PITCH: the 8 light pipes are one part on this pitch
N_PIPES = 8
STOP_GAP = 0.6                 # STOP_GAP: button travel to its hard stop
HAT_BOT_Z = -1.6               # the HAT is 1.6 thick, z = 0 on its top face
# export_lid() puts the lid's lower-left corner at (5, 5) on the laser sheet
LID_DXF_AT = (LID[0] - 5.0, LID[2] - 5.0)          # (-14.9, 10.3): sheet -> world
LID_CENTRE = ((LID[0] + LID[1]) / 2, (LID[2] + LID[3]) / 2)

# --- Raspberry Pi 4B (SPEC section 3, extract_board_mech.py) -------------------
# pi4b.step frame: x = long axis (SD end 0 .. USB end 85), y = up (PCB top at 0),
# z = short axis (-56 .. 0, port edge at 0). In the board frame:
#   X = z + 140.0,  Y = x + 71.0,  Z = y - 12.6
# i.e. a 120 degree turn about (1, 1, 1) (x->y, y->z, z->x), then a move.
PI_TURN_AXIS = [1, 1, 1]
PI_TURN = '120 deg'
PI_MOVE = [140.0, 71.0, -12.6]  # Pi PCB top = HAT bottom (-1.6) - 11 mm standoff

# --- looks (enclosure.py build_all colours, AESTHETIC.md) ----------------------
LOOK = {
    'tray': '#0a0a0b',          # matte black PETG
    'faceplate': '#b3b5b8',     # silver / aluminium PETG
    'pipe_1': '#e6e6d9',        # natural PETG
    'button_sw1': '#d9611a',    # copper / orange accent PETG
    'button_sw2': '#d9611a',
}


def cmd(c, **p):
    return {'command': c, 'params': p}


def build(with_boards=True):
    s = []
    s.append(cmd('document.metadata.set', values={
        'project': 'Vinyl ADC', 'part_number': 'VADC-ENC-D', 'revision': 'D',
        'author': 'Mads Rudolph',
        'description': 'Rev D enclosure assembly: tray, faceplate, 8 light pipes, 2 buttons, '
                       'acrylic lid, the rev D HAT and a Raspberry Pi 4B. Built by '
                       'solidcraft/build_assembly.json from cad/enclosure.py outputs.'}))
    s.append(cmd('parameters.add', name='lid_t', expression=f'{LID_T} mm',
                 comment='acrylic lid thickness (enclosure.py LID_T)', favorite=True))
    s.append(cmd('parameters.add', name='lid_under_z', expression=f'{LID_UNDER_Z} mm',
                 comment='lid underside height above the HAT top (enclosure.py LID_UNDER_Z)'))
    s.append(cmd('parameters.add', name='led_pitch', expression=f'{LED_PITCH} mm',
                 comment='light pipe pitch (enclosure.py LED_PITCH)'))
    s.append(cmd('material.create', name='PETG', density_g_cm3=1.27, color='#202022'))
    s.append(cmd('material.create', name='Cast acrylic', density_g_cm3=1.18,
                 color='#d9ebf2', opacity=0.3))

    # 1. the printed parts, already placed, from enclosure.step ------------------
    s.append(cmd('file.insert_step', path=str(ENCLOSURE_STEP), name='enclosure', names='product'))
    # its rigid group would freeze the buttons; break it and joint the parts one by one
    s.append(cmd('component.unlock', component='enclosure'))
    # enclosure.step also carries a lid solid; the lid here is made from the laser DXF instead
    s.append(cmd('solid.remove', bodies=['lid_acrylic']))
    s.append(cmd('component.delete', component='lid_acrylic'))
    # enclosure.step holds only pipe_1 (the 8 pipes are identical); place it 7 more times
    for i in range(1, N_PIPES):
        s.append(cmd('occurrence.copy', component='pipe_1', translate=[round(LED_PITCH * i, 3), 0, 0]))
    s.append(cmd('component.rename', component='pipe_1', name='light_pipe'))

    # 2. the acrylic lid, from the laser-cut DXF --------------------------------
    s.append(cmd('component.activate', component='root'))
    s.append(cmd('component.create', name='lid_acrylic'))
    s.append(cmd('sketch.create', plane='XY', offset='lid_under_z', name='lid outline (lid.dxf CUT)'))
    s.append(cmd('sketch.insert_dxf', path=str(LID_DXF), at=list(LID_DXF_AT)))
    s.append(cmd('sketch.finish'))
    s.append(cmd('solid.extrude', distance='lid_t', profiles=[{'point': list(LID_CENTRE)}],
                 operation='new'))
    s.append(cmd('body.rename', body='Body1', name='lid_acrylic'))
    s.append(cmd('component.activate', component='root'))

    # 3. boards -----------------------------------------------------------------
    if with_boards:
        s.append(cmd('file.insert_step', path=str(HAT_STEP), name='hat_rev_d'))
        s.append(cmd('occurrence.move', occurrence='hat_rev_d:1', space='world',
                     translate=[0, 0, HAT_BOT_Z]))
        s.append(cmd('file.insert_step', path=str(PI_STEP), name='raspberry_pi_4b'))
        s.append(cmd('occurrence.move', occurrence='raspberry_pi_4b:1', space='world',
                     axis=PI_TURN_AXIS, angle=PI_TURN, origin=[0, 0, 0]))
        s.append(cmd('occurrence.move', occurrence='raspberry_pi_4b:1', space='world',
                     translate=PI_MOVE))

    # 4. mates. Every part was put where enclosure.py / SPEC says, so the joints are
    #    "as built": they lock the relation without moving anything.
    s.append(cmd('occurrence.ground', occurrence='enclosure:1', grounded=True))
    s.append(cmd('occurrence.ground', occurrence='tray:1', grounded=True))
    J = lambda t, a, b, name, **k: s.append(cmd('joint.as_built', type=t, a=a, b=b, name=name, **k))
    J('rigid', 'tray:1', 'faceplate:1', 'faceplate to tray (2 floor-tab screws)')
    for i in range(1, N_PIPES + 1):
        J('rigid', 'faceplate:1', f'light_pipe:{i}', f'light pipe {i} in faceplate bore')
    for sw in ('sw1', 'sw2'):
        # slides along its stem (z); 0 = at rest, -STOP_GAP = cap on its hard stop
        J('slider', 'faceplate:1', f'button_{sw}:1', f'button {sw.upper()} in guide bore',
          limits=[[-STOP_GAP, 0]])
    J('rigid', 'tray:1', 'lid_acrylic:1', 'lid in rebate (4 x M3)')
    if with_boards:
        J('rigid', 'tray:1', 'hat_rev_d:1', 'HAT on M3 posts H1/H2/H3')
        J('rigid', 'hat_rev_d:1', 'raspberry_pi_4b:1', 'Pi on J2 + 11 mm standoffs')

    # 5. looks and materials
    for body, colour in LOOK.items():
        s.append(cmd('appearance.assign', bodies=[body], color=colour))
    s.append(cmd('material.assign', bodies=list(LOOK), material='PETG'))
    s.append(cmd('material.assign', bodies=['lid_acrylic'], material='Cast acrylic'))
    s.append(cmd('appearance.assign', bodies=['lid_acrylic'], appearance='Glass - Clear'))
    s.append(cmd('component.rename', component='root', name='vinyl_adc_rev_d_assembly'))
    s.append(cmd('joint.solve'))

    # 6. named views for the GUI (View menu / view cube); also used by render_overview.py
    for name, cam in VIEWS.items():
        s.append(cmd('view.save', name=name, camera=cam))
    return s


# cameras: mm and radians; yaw 0 looks from the front, -pi/4 is the front-right iso
_T = [66.0, 78.0, 0.0]
VIEWS = {
    'Overview': dict(target=_T, yaw=-0.785398, pitch=0.6155, distance=380.0, fov=0.0),
    'Rear ports': dict(target=_T, yaw=-2.35619, pitch=0.42, distance=380.0, fov=0.0),
    'Front panel': dict(target=_T, yaw=0.0, pitch=0.15, distance=380.0, fov=0.0),
    'Top': dict(target=_T, yaw=0.0, pitch=1.5707, distance=380.0, fov=0.0),
}


if __name__ == '__main__':
    boards = '--no-boards' not in sys.argv
    out = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else SC / 'build_assembly.json'
    out.write_text(json.dumps({'commands': build(boards)}, indent=1))
    print('wrote', out)
