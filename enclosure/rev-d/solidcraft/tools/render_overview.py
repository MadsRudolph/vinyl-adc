"""Render the overview images of the SolidCraft assembly.

    enclosure/rev-d/.venv/bin/python enclosure/rev-d/solidcraft/tools/render_overview.py

Each shot replays build_assembly.json (about 20 s), hides some parts and takes a
viewport snapshot with solidcraft-cli, one job at a time under tools/capped (3 GB).
`solidcraft-cli render` (the product renderer) cannot be used: the Pi 4B model is
over its 262144-triangle cap. Writes solidcraft/render/*.png and a 2 x 2 sheet,
solidcraft/overview.png.
"""
import os
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SC = HERE.parent
REPO = SC.parents[2]
CAPPED = REPO / 'tools' / 'capped'
BUILD = json.loads((SC / 'build_assembly.json').read_text())['commands']
OUT = SC / 'render'
W, H = int(os.environ.get("SNAP_W", 1600)), int(os.environ.get("SNAP_H", 1000))

PIPES = ['pipe_1']
SHOTS = [
    # file, caption, saved view, bodies to hide
    ('closed', 'Closed: faceplate, buttons, light pipes, acrylic lid', 'Overview', []),
    ('lid_off', 'Lid off: the rev D HAT in the tray', 'Overview', ['lid_acrylic']),
    ('rear', 'Rear: Pi 4 Ethernet and USB, RCA and ground post', 'Rear ports', []),
    ('stack', 'Tray and lid hidden: HAT, Pi 4, faceplate, buttons', 'Overview',
     ['lid_acrylic', 'tray']),
]


def shot(name, view, hide):
    cmds = list(BUILD)
    if hide:
        cmds.append({'command': 'browser.visibility', 'params': {'visible': False, 'items': hide}})
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump({'commands': cmds}, f)
    png = OUT / f'{name}.png'
    subprocess.run([str(CAPPED), '-m', '3G', 'solidcraft-cli', 'snapshot', f.name, '--out', str(png),
                    '--view', view, '--width', str(W), '--height', str(H), '--no-grid', '--no-axes'],
                   check=True, stdout=subprocess.DEVNULL)
    Path(f.name).unlink()
    return png


def main():
    OUT.mkdir(exist_ok=True)
    pngs = []
    for name, caption, view, hide in SHOTS:
        print('render', name, flush=True)
        pngs.append((shot(name, view, hide), caption))
    # 2 x 2 sheet, cropped a little, with captions
    cw, ch = 1200, 760
    sheet = Image.new('RGB', (2 * cw, 2 * ch), 'white')
    try:
        font = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Medium.ttf', 30)
    except OSError:
        font = ImageFont.load_default()
    for i, (png, caption) in enumerate(pngs):
        im = Image.open(png).convert('RGB')
        x0, y0 = (W - cw) // 2, (H - ch) // 2 + 40
        im = im.crop((x0, y0, x0 + cw, y0 + ch))
        d = ImageDraw.Draw(im)
        d.text((28, 22), caption, fill=(30, 32, 36), font=font)
        sheet.paste(im, ((i % 2) * cw, (i // 2) * ch))
    sheet.save(SC / 'overview.png', optimize=True)
    print('wrote', SC / 'overview.png')


if __name__ == '__main__':
    main()
