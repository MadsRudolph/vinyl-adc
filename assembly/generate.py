#!/usr/bin/env python3
"""Read-only extraction from KiCad; run with the system Python with pcbnew."""
from pathlib import Path
import hashlib,json,datetime,subprocess,collections
import pcbnew as p
p.SwigPyIterator.next=p.SwigPyIterator.__next__  # KiCad 10 / Python 3.14 SWIG compatibility
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assembly/generated';OUT.mkdir(exist_ok=True)
def xy(v): return [round(p.ToMM(v.x),4),round(p.ToMM(v.y),4)]
def natural(s):
 import re
 return [int(x) if x.isdigit() else x for x in re.split('(\\d+)',s)]
result={'generated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boards':{}}
for name in ['power','channel_l','digital']:
 path=ROOT/f'hardware/kicad/{name}/vinyl_adc_{name}.kicad_pcb'
 b=p.LoadBoard(str(path));tracks=b.GetTracks()
 assert all(not z.GetLayerSet().Contains(p.F_Cu) for z in b.Zones()), 'Top pours need explicit joint extraction'
 assert not any(isinstance(t,p.PCB_VIA) for t in tracks), 'Vias need explicit assembly instructions'
 top=[t for t in tracks if t.GetLayer()==p.F_Cu and not isinstance(t,p.PCB_VIA)]
 parts=[];allpads=[]
 for f in sorted(b.GetFootprints(),key=lambda f:natural(f.GetReference())):
  pads=[]
  for pad in f.Pads():
   hits=[t for t in top if t.GetNetCode()==pad.GetNetCode() and (pad.HitTest(t.GetStart()) or pad.HitTest(t.GetEnd()) or t.HitTest(pad.GetPosition()))]
   d={'pin':pad.GetNumber(),'net':pad.GetNetname(),'at':xy(pad.GetPosition()),'size':xy(pad.GetSize()),'angle':pad.GetOrientationDegrees(),'drill':xy(pad.GetDrillSize()),'top':bool(hits),'ref':f.GetReference()}
   pads.append(d);allpads.append((pad,d))
  fp=str(f.GetFPID().GetLibItemName());ref=f.GetReference()
  kind='mount' if ref.startswith('H') else 'wire' if ref.startswith('WL') else 'socket' if ref.startswith(('U','X')) else 'resistor' if ref.startswith('R') and not ref.startswith('RV') else 'diode' if ref.startswith('D') else 'electrolytic' if fp.startswith('CP_') else 'capacitor' if ref.startswith('C') else 'connector'
  parts.append({'ref':ref,'value':f.GetValue(),'footprint':fp,'at':xy(f.GetPosition()),'angle':f.GetOrientationDegrees(),'kind':kind,'pads':pads})
 # Connected top-layer routes; retain exact geometry and terminal identities.
 pending=set(range(len(top)));runs=[]
 while pending:
  group={pending.pop()};changed=True
  while changed:
   changed=False
   points={(tuple(xy(top[i].GetStart())),top[i].GetNetCode()) for i in group}|{(tuple(xy(top[i].GetEnd())),top[i].GetNetCode()) for i in group}
   for i in list(pending):
    t=top[i]
    if any(t.GetNetCode()==top[j].GetNetCode() and (top[j].HitTest(t.GetStart()) or top[j].HitTest(t.GetEnd()) or t.HitTest(top[j].GetStart()) or t.HitTest(top[j].GetEnd())) for j in group):
     group.add(i);pending.remove(i);changed=True
  ends=[]
  for pad,d in allpads:
   if any(top[i].GetNetCode()==pad.GetNetCode() and (pad.HitTest(top[i].GetStart()) or pad.HitTest(top[i].GetEnd()) or top[i].HitTest(pad.GetPosition())) for i in group): ends.append(d)
  runs.append({'net':top[next(iter(group))].GetNetname(),'pads':ends,'length':round(sum(p.ToMM(top[i].GetLength()) for i in group),1)})
 box=b.GetBoardEdgesBoundingBox()
 drcpath=OUT/f'{name}-drc.json'
 subprocess.run(['kicad-cli','pcb','drc','--format','json','-o',str(drcpath),str(path)],check=True,capture_output=True)
 drc=json.loads(drcpath.read_text())
 data={'source':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'parts':parts,'bounds':[*xy(box.GetPosition()),*xy(box.GetSize())], 'tracks':[{'a':xy(t.GetStart()),'b':xy(t.GetEnd()),'layer':'top' if t.GetLayer()==p.F_Cu else 'bottom','net':t.GetNetname()} for t in tracks if not isinstance(t,p.PCB_VIA)],'vias':[{'at':xy(t.GetPosition()),'net':t.GetNetname()} for t in tracks if isinstance(t,p.PCB_VIA)],'runs':runs,'drc':{'unconnected':drc.get('unconnected_items',[]),'violations':drc.get('violations',[])}}
 result['boards'][name]=data
 print(name,'parts',len(parts),'top pads',sum(d['top'] for _,d in allpads),'runs',len(runs),'vias',len(data['vias']))
 print('socket top:',', '.join(d['ref']+'.'+d['pin'] for _,d in allpads if d['top'] and d['ref'].startswith(('U','X'))))
(OUT/'boards.json').write_text(json.dumps(result,indent=2)+'\n')
