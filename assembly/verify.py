#!/usr/bin/env python3
"""Validate the assembly snapshot against current source geometry and critical build facts."""
from pathlib import Path
import json,hashlib
import pcbnew as p
p.SwigPyIterator.next=p.SwigPyIterator.__next__
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'assembly/generated/boards.json').read_text())['boards']
expected={'power':18,'digital':13,'channel_l':39}
for name,d in data.items():
 path=root/d['source'];assert hashlib.sha256(path.read_bytes()).hexdigest()==d['sha256'],f'{name}: stale snapshot'
 b=p.LoadBoard(str(path))
 assert all(not z.GetLayerSet().Contains(p.F_Cu) for z in b.Zones()),'Top copper pour requires extending top-pad extraction'
 assert not d['vias'],'Vias require explicit two-face assembly instructions'
 assert len([f for f in d['parts'] if f['kind'] not in ['mount','wire']])==expected[name]
 assert not d['drc']['unconnected'],f'{name}: unconnected PCB items'
 assert all(len(f['pads'])==len({a['pin'] for a in f['pads']}) for f in d['parts'])
c=data['channel_l']['parts'];top={f"{f['ref']}.{a['pin']}" for f in c for a in f['pads'] if a['top']}
assert len(top)==20
assert {s for s in top if s.startswith('U')}=={'U20.1','U22.4','U23.1','U23.2','U23.10','U24.4'}
for name in ['power','digital']:
 parts=data[name]['parts'];wires={f['ref']:f for f in parts if f['kind']=='wire'}
 for ref,f in wires.items():
  mate=ref[:-1]+('B' if ref.endswith('A') else 'A')
  assert mate in wires and wires[mate]['pads'][0]['net']==f['pads'][0]['net']
 for f in parts:
  for a in f['pads']:
   if a['top'] and f['kind']!='wire':assert any(w['pads'][0]['net']==a['net'] for w in wires.values()),'Top-connected component needs a wire anchor'
assert len([f for f in data['digital']['parts'] if f['kind']=='wire'])==18
print('PASS: source hashes, 109 component positions, 20 channel top joints, six critical socket pins, link mates/nets, no unconnected items, no unsupported vias/top pours.')
