"""Rebuild the printable lattice shell and assembled scene with Blender.
blender --factory-startup -b --python enclosure/build_enclosure.py -- --standoff 23
All design coordinates are millimetres. Original assembly is a retained source asset.
"""
import argparse, math, sys, json, struct, zipfile
from pathlib import Path
import bpy, bmesh
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--standoff',type=float,default=23,help='Inter-board spacer length in mm (original: 11)')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'enclosure/source/original_assembly.blend'))
bpy.context.preferences.filepaths.save_version=0
s=bpy.context.scene; s.frame_set(1)
base=bpy.data.objects['Enclosure_3D_Print_Base']

def activate(o):
 bpy.ops.object.select_all(action='DESELECT'); o.hide_set(False); o.select_set(True); bpy.context.view_layer.objects.active=o

def boolean(o,cutter,operation='DIFFERENCE'):
 activate(o); m=o.modifiers.new('Organic openings','BOOLEAN'); m.operation=operation; m.solver='EXACT'; m.object=cutter
 bpy.ops.object.modifier_apply(modifier=m.name)

def box(name,lo,hi):
 bpy.ops.mesh.primitive_cube_add(size=1,location=tuple((x+y)/2 for x,y in zip(lo,hi)))
 o=bpy.context.object; o.name=name; o.dimensions=tuple(y-x for x,y in zip(lo,hi)); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); return o

# Extend the original wall and cavity while preserving the floor, bevels,
# connector hole diameters, corner lands and the existing acrylic pocket.
for v in base.data.vertices:
 if v.co.z>4: v.co.z+=40
cavity=bpy.data.objects['Cutter_Inner_Cavity']
for v in cavity.data.vertices:
 if v.co.z>4.01: v.co.z+=40
bpy.data.objects['Cutter_Lid_Recess'].location.z+=40
for v in bpy.data.objects['Cutter_HeatSet_Inserts'].data.vertices:
 if v.co.z>50: v.co.z+=40
# Connector cutouts stay at their original coordinates; cables span the taller stack.
delta=a.standoff-11
activate(base)
for m in list(base.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)

# Retain only the floor and lid-support ring from the original shell.
# Everything between them is an actual skeletal network, not a perforated wall.
cut=box('Remove wall skin',(-90,-90,9),(90,90,94))
boolean(base,cut); bpy.data.objects.remove(cut,do_unlink=True)
parts=[base]
protected={'right':[(0,50,16,48)],'front':[(-36,-14,21,43)],'back':[(-43,23,44,66)],'left':[]}

def rounded_panel(side,u0,u1,z0,z1):
 if side in ('front','back'):
  y=-69 if side=='front' else 69
  o=box('Connector mounting island',(u0,y-3,z0),(u1,y+3,z1))
 else:
  o=box('Connector mounting island',(66,u0,z0),(72,u1,z1))
 activate(o); mod=o.modifiers.new('Rounded island edges','BEVEL'); mod.width=3; mod.segments=5
 bpy.ops.object.modifier_apply(modifier=mod.name); parts.append(o)
for side,lands in protected.items():
 for land in lands: rounded_panel(side,*land)

# Organic cellular network on an unwrapped perimeter. Voronoi cells meet in
# three-way branches; gently bowed ribs form irregular, open windows.
# Periodic seeds keep the network continuous around all four corners.
import random
rng=random.Random(19)
period=552.0
seeds=[]
for row,z in enumerate((8,36,65,94)):
 for col in range(14):
  seeds.append(((col+(0.5 if row%2 else 0))*period/14+rng.uniform(-7,7),z+rng.uniform(-5,5)))
all_seeds=[(x+offset,z) for offset in (-period,0,period) for x,z in seeds]

def clip(poly,A,B,C):
 out=[]
 for v,w in zip(poly,poly[1:]+poly[:1]):
  fv=A*v[0]+B*v[1]-C; fw=A*w[0]+B*w[1]-C
  if fv<=1e-7: out.append(v)
  if (fv<0)!=(fw<0):
   t=fv/(fv-fw); out.append((v[0]+t*(w[0]-v[0]),v[1]+t*(w[1]-v[1])))
 return out

def surface(u,z):
 # Rounded-square perimeter, tangent continuity at every corner.
 # Scale to 138 mm centreline width; each side includes two quarter corners.
 u=u%period; side=int(u//138); t=u%138
 r=10; straight=118; arc=math.pi*r/2; length=straight+arc
 q=t/138*length
 if q<straight: x=-59+q; y=-69
 else:
  theta=-math.pi/2+(q-straight)/r
  x=59+r*math.cos(theta); y=-59+r*math.sin(theta)
 for _ in range(side): x,y=-y,x
 return (x,y,z)

rib_samples=[]
def rib(v,w):
 u0,z0=v; u1,z1=w
 if math.hypot(u1-u0,z1-z0)<1: return
 cu=bpy.data.curves.new('Flowing structural rib','CURVE'); cu.dimensions='3D'; cu.resolution_u=12; cu.bevel_depth=2.7; cu.bevel_resolution=3; cu.use_fill_caps=True
 sp=cu.splines.new('POLY'); sp.points.add(12)
 # Zero displacement at branch nodes keeps the network connected.
 bend=1.6*math.sin((u0+u1)*0.041+(z0+z1)*0.07)
 for i,pt in enumerate(sp.points):
  t=i/12; u=u0+(u1-u0)*t+bend*math.sin(math.pi*t); z=z0+(z1-z0)*t
  pt.co=(*surface(u,z),1)
  # Thicken the rib gradually as it approaches a connector mounting island.
  px,py,pz=pt.co[:3]
  distance=min(math.dist((px,py,pz),centre) for centre in ((-25,-69,32),(69,25,32),(-10,69,55)))
  pt.radius=1+0.3*max(0,1-distance/32)
  if i in (3,6,9):
   tangent=Vector(surface(u0+(u1-u0)*(t+0.01),z0+(z1-z0)*(t+0.01)))-Vector(surface(u0+(u1-u0)*(t-0.01),z0+(z1-z0)*(t-0.01)))
   rib_samples.append((Vector(pt.co[:3]),tangent.normalized()))
 o=bpy.data.objects.new('Organic rib',cu); s.collection.objects.link(o); activate(o); bpy.ops.object.convert(target='MESH'); parts.append(bpy.context.object)

edges=set()
for x,z in all_seeds:
 if x < -60 or x > period+60: continue
 poly=[(0,7),(period,7),(period,96),(0,96)]
 for xx,zz in all_seeds:
  if abs(x-xx)+abs(z-zz)<1e-6: continue
  poly=clip(poly,xx-x,zz-z,(xx*xx+zz*zz-x*x-z*z)/2)
  if not poly: break
 for v,w in zip(poly,poly[1:]+poly[:1]):
  # Periodic seam boundaries are not physical ribs.
  if abs(v[0]-w[0])<1e-6 and (abs(v[0])<1e-6 or abs(v[0]-period)<1e-6): continue
  # Horizontal boundary ribs blend into the floor and top rim.
  key=tuple(sorted((tuple(round(c,3) for c in v),tuple(round(c,3) for c in w))))
  if key not in edges: edges.add(key); rib(v,w)
# Load paths below the four lid inserts keep insertion force and lid screw
# loads out of the smaller lattice branches. They bow gently with the lattice.
for x in (-64,64):
 for y in (-64,64):
  cu=bpy.data.curves.new('Lid insert load path','CURVE'); cu.dimensions='3D'; cu.bevel_depth=3.4; cu.bevel_resolution=4; cu.use_fill_caps=True
  sp=cu.splines.new('POLY'); sp.points.add(24)
  for i,pt in enumerate(sp.points):
   t=i/24; bow=1.0*math.sin(math.pi*t)
   pt.co=(x+math.copysign(bow,x),y+math.copysign(bow,y),7+90*t,1)
  o=bpy.data.objects.new('Organic corner support',cu); s.collection.objects.link(o); activate(o); bpy.ops.object.convert(target='MESH'); parts.append(bpy.context.object)
  bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=6,depth=12,location=(x,y,96))
  parts.append(bpy.context.object)
# Fuse intersections into smooth, rounded branch junctions, then recut exact
# connector and insert bores so voxel fusion cannot shrink their diameters.
bpy.ops.object.select_all(action='DESELECT')
for o in parts: o.select_set(True)
bpy.context.view_layer.objects.active=base; bpy.ops.object.join()
mod=base.modifiers.new('Fuse organic branches','REMESH'); mod.mode='VOXEL'; mod.voxel_size=0.3; mod.use_smooth_shade=True
bpy.ops.object.modifier_apply(modifier=mod.name)
mod=base.modifiers.new('Soften branch junctions','SMOOTH'); mod.factor=0.65; mod.iterations=4
bpy.ops.object.modifier_apply(modifier=mod.name)
mod=base.modifiers.new('Compact printable mesh','DECIMATE'); mod.ratio=0.08
bpy.ops.object.modifier_apply(modifier=mod.name)
for name in ('Cutter_Ports','Cutter_HeatSet_Inserts','Cutter_Lid_Recess'):
 boolean(base,bpy.data.objects[name])
# Remove a decorative floating badge from the old closed front wall.
bpy.data.objects.remove(bpy.data.objects['Enclosure_Front_Badge'],do_unlink=True)
# Offset assembled and exploded keyframes together so the existing animation survives.
def shift(o,dz):
 o.location.z+=dz
 if o.animation_data and o.animation_data.action:
  act=o.animation_data.action
  for layer in act.layers:
   for strip in layer.strips:
    for bag in strip.channelbags:
     for fc in bag.fcurves:
      if fc.data_path=='location' and fc.array_index==2:
       for k in fc.keyframe_points:
        k.co.y+=dz; k.handle_left.y+=dz; k.handle_right.y+=dz
for o in list(s.objects):
 if o.parent: continue
 name=o.name
 if name.startswith(('Plexiglass','M3_Lid_','M3_Heated_Insert_Top','M3_Bore_Top')): shift(o,40)
 elif name.startswith('Real_PCB_'): shift(o,(int(name[9])-1)*delta)
 elif name.startswith('Standoff_Tier'):
  tier=int(name[len('Standoff_Tier')]); shift(o,(tier-1)*delta)
  # Mesh origin is at the bottom of each spacer.
  o.data=o.data.copy()
  for v in o.data.vertices: v.co.z*=a.standoff/11
 elif name.startswith(('M3_Top_Nut','M3_PCB_Top_Nut','Pi_Ribbon')): shift(o,3*delta)
# Wires are illustrative. Lift board-end control points with their PCB tier.
for o in s.objects:
 if o.name.startswith('Wire_') and o.type=='CURVE':
  for spline in o.data.splines:
   for pt in spline.bezier_points:
    x,y,z=pt.co; weight=max(0,min(1,(70-max(abs(x),abs(y)))/16))
    dz=(delta if 'RCA_R_' in o.name else 2*delta if 'RCA_L_' in o.name or 'Pot_' in o.name else 0)*weight
    pt.co.z+=dz; pt.handle_left.z+=dz; pt.handle_right.z+=dz
s.frame_set(1); bpy.context.view_layer.update()
# Evaluate the actual manufactured mesh, not the hardware visualization.
activate(base)
bm=bmesh.new(); bm.from_mesh(base.data); bmesh.ops.triangulate(bm,faces=list(bm.faces)); bm.to_mesh(base.data)
assert all(e.is_manifold for e in bm.edges),'Non-manifold print mesh'
seen=set(); components=0
for v in bm.verts:
 if v in seen: continue
 components+=1; todo=[v]; seen.add(v)
 while todo:
  for e in todo.pop().link_edges:
   for w in e.verts:
    if w not in seen: seen.add(w); todo.append(w)
assert components==1, f'{components} disconnected printable components'
volume=bm.calc_volume(signed=True); assert volume>0
bm.free()
# Sample cross-sections of the finished ribs after fusion and simplification.
from mathutils.bvhtree import BVHTree
bvh=BVHTree.FromObject(base,bpy.context.evaluated_depsgraph_get())
widths=[]
for centre,tangent in rib_samples:
 reference=Vector((0,0,1)) if abs(tangent.z)<0.95 else Vector((1,0,0))
 normal=tangent.cross(reference).normalized(); second=tangent.cross(normal).normalized()
 for k in range(8):
  d=normal*math.cos(k*math.pi/8)+second*math.sin(k*math.pi/8)
  hit1=bvh.ray_cast(centre,d,25); hit2=bvh.ray_cast(centre,-d,25)
  if hit1[0] is not None and hit2[0] is not None: widths.append(hit1[3]+hit2[3])
minimum_width=min(widths)
assert minimum_width>4.4, f'Rib cross-section too thin: {minimum_width}'
verts=[tuple(base.matrix_world @ v.co) for v in base.data.vertices]
faces=[tuple(p.vertices) for p in base.data.polygons]
stl=ROOT/'enclosure/vinyl_adc_enclosure_base.stl'
with stl.open('wb') as f:
 f.write(b'Vinyl ADC organic lattice, millimetres'.ljust(80,b'\0')); f.write(struct.pack('<I',len(faces)))
 for ids in faces:
  va,vb,vc=[Vector(verts[i]) for i in ids]; normal=(vb-va).cross(vc-va).normalized()
  f.write(struct.pack('<12fH',*normal,*va,*vb,*vc,0))
model='<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources><object id="1" type="model"><mesh><vertices>'
model+=''.join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x,y,z in verts)
model+='</vertices><triangles>'+''.join(f'<triangle v1="{x}" v2="{y}" v3="{z}"/>' for x,y,z in faces)+'</triangles></mesh></object></resources><build><item objectid="1"/></build></model>'
with zipfile.ZipFile(ROOT/'enclosure/vinyl_adc_enclosure_base.3mf','w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
 z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
 z.writestr('3D/3dmodel.model',model)
# Record actual top-component bounds for the assembled stack.
board_bounds={}
for root in [o for o in s.objects if o.name.startswith('Real_PCB_') and not o.parent]:
 coords=[child.matrix_world @ Vector(v) for child in root.children_recursive if child.type=='MESH' for v in child.bound_box]
 board_bounds[root.name]={'bottom':min(v.z for v in coords),'top':max(v.z for v in coords)}
clearance=102-max(v['top'] for v in board_bounds.values())
assert clearance>=2, f'Insufficient lid clearance: {clearance}'
report={'dimensions_mm':[144,144,105],'nominal_rib_diameter_mm':5.4,'sampled_minimum_rib_width_mm':minimum_width,'rib_width_samples':len(widths),'corner_support_diameter_mm':6.8,'lid_insert_boss_diameter_mm':12,'supports_required':True,'height_increase_mm':40,'lid_underside_mm':102,'inter_board_standoff_mm':a.standoff,'board_bounds_mm':board_bounds,'lid_clearance_mm':clearance,'mesh_components':components,'watertight':True,'triangles':len(faces),'volume_mm3':volume,'lid_insert_pilot_diameter_mm':4.2,'lid_insert_centres_mm':[[x,y] for x in (-64,64) for y in (-64,64)],'connector_lands':protected}
(ROOT/'enclosure/validation.json').write_text(json.dumps(report,indent=2)+'\n')
base['design']='Organic lattice / 105 mm'; base['inter_board_standoff_mm']=a.standoff
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'enclosure/vinyl_adc_enclosure.blend'))
# Export only visible assembly objects, with the existing explosion animation.
bpy.ops.object.select_all(action='DESELECT')
for o in s.objects:
 if not o.hide_render and not o.name.startswith('Cutter_') and o.type not in {'LIGHT','CAMERA'}: o.hide_set(False); o.select_set(True)
exec(compile((ROOT/'enclosure/export_web_model.py').read_text(),str(ROOT/'enclosure/export_web_model.py'),'exec'))
print('VALIDATION',json.dumps(report))
