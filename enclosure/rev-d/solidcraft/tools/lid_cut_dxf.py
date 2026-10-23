"""Copy ../out/lid.dxf keeping only the CUT layer (outline + 4 screw holes).

SolidCraft's Insert DXF reads every layer, and the ENGRAVE layer (wordmark and
corner marks) would turn into dozens of extra sketch profiles. The laser file
in out/ is left untouched; this writes solidcraft/parts/lid_cut.dxf.

    enclosure/rev-d/.venv/bin/python enclosure/rev-d/solidcraft/tools/lid_cut_dxf.py
"""
from pathlib import Path
import ezdxf

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / 'out' / 'lid.dxf'
DST = HERE.parent / 'parts' / 'lid_cut.dxf'

doc = ezdxf.readfile(SRC)
msp = doc.modelspace()
kept = dropped = 0
for e in list(msp):
    if e.dxf.layer.upper() == 'CUT':
        kept += 1
    else:
        msp.delete_entity(e)
        dropped += 1
DST.parent.mkdir(exist_ok=True)
doc.saveas(DST)
print(f'{DST}: kept {kept} CUT entities, dropped {dropped}')
for e in msp:
    print(' ', e.dxftype(), getattr(e.dxf, 'center', ''), getattr(e.dxf, 'radius', ''))
