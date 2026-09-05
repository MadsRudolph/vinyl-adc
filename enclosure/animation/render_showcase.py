"""Run with blender -b enclosure/vinyl_adc_enclosure.blend --python enclosure/animation/render_showcase.py -- [--preview] [--clip orbit|assembly|electronics]."""
import bpy, math, sys, argparse
from pathlib import Path
from mathutils import Vector
p=argparse.ArgumentParser(); p.add_argument('--preview',action='store_true'); p.add_argument('--clip',choices=['orbit','assembly','electronics']); a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
root=Path(__file__).resolve().parents[2]; out=root/'media/showcase'; out.mkdir(exist_ok=True)
s=bpy.context.scene; s.frame_set(1); bpy.context.preferences.filepaths.save_version=0
# Capture the design's own explosion endpoints before replacing its animation.
base={o.name:o.location.copy() for o in s.objects}
s.frame_set(55); exploded={o.name:o.location.copy() for o in s.objects}; s.frame_set(1)
for o in s.objects: o.animation_data_clear()
cam=s.camera; cam.constraints.clear(); cam.data.type='ORTHO'; cam.data.clip_end=5000
s.render.engine='BLENDER_EEVEE'; s.eevee.taa_render_samples=64; s.render.resolution_x=960; s.render.resolution_y=720; s.render.resolution_percentage=100; s.render.fps=24
s.render.image_settings.file_format='PNG'; s.render.film_transparent=False
s.world.use_nodes=True; s.world.node_tree.nodes.get('Background').inputs[0].default_value=(0.045,0.06,0.085,1); s.world.node_tree.nodes.get('Background').inputs[1].default_value=0.45
for o in s.objects:
 if o.type=='LIGHT':
  o.data.energy= {'Key_Light':1800000,'Fill_Light':1000000,'Rim_Light':2200000}.get(o.name,1000000)
  o.data.shape='DISK'; o.data.size=200
s.view_settings.view_transform='AgX'
# A neutral studio floor provides readable silhouettes and soft contact shadows.
bpy.ops.mesh.primitive_plane_add(size=20000,location=(0,0,-1)); floor=bpy.context.object; floor.name='Showcase_Studio_Floor'
m=bpy.data.materials.new('Showcase_Slate'); m.diffuse_color=(0.022,0.032,0.048,1); m.use_nodes=True; m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=m.diffuse_color; m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=0.75; floor.data.materials.append(m)
# Transparent acrylic with a restrained surface reflection, suitable for Eevee.
m=bpy.data.materials.get('Mat_Plexiglass_Clear')
if m:
 n=m.node_tree.nodes; n.clear(); output=n.new('ShaderNodeOutputMaterial'); mix=n.new('ShaderNodeMixShader'); mix.inputs[0].default_value=0.12; tr=n.new('ShaderNodeBsdfTransparent'); bs=n.new('ShaderNodeBsdfPrincipled'); bs.inputs['Base Color'].default_value=(0.48,0.7,0.8,1); bs.inputs['Roughness'].default_value=0.17; bs.inputs['Metallic'].default_value=0.25
 m.node_tree.links.new(tr.outputs[0],mix.inputs[1]); m.node_tree.links.new(bs.outputs[0],mix.inputs[2]); m.node_tree.links.new(mix.outputs[0],output.inputs[0]); m.surface_render_method='BLENDED'
original_hidden={o.name:o.hide_render for o in s.objects}
for clip in ([a.clip] if a.clip else ['orbit','assembly','electronics']):
 for o in s.objects:
  o.animation_data_clear(); o.hide_render=original_hidden[o.name]
  if o.name in base:o.location=base[o.name]
 for f in range(1,146):
  t=(f-1)/144; pulse=(1-math.cos(2*math.pi*t))/2
  amount= pulse if clip=='assembly' else (0.85 if clip=='electronics' else 0)
  for o in s.objects:
   if o.name in base:
    o.location=base[o.name]+(exploded[o.name]-base[o.name])*amount
    o.keyframe_insert(data_path='location',frame=f)
  if clip=='electronics':
   for o in s.objects:
    ancestor=o
    while ancestor.parent: ancestor=ancestor.parent
    if not ancestor.name.startswith('Real_PCB') and o.type not in {'CAMERA','LIGHT'} and o!=floor: o.hide_render=True
   angle=math.radians(-55+22*math.sin(2*math.pi*t)); target=Vector((0,0,65)); cam.data.ortho_scale=245; elevation=300
  elif clip=='assembly':
   angle=math.radians(-55+8*math.sin(2*math.pi*t)); target=Vector((0,0,47+35*pulse)); cam.data.ortho_scale=335; elevation=235
  else:
   angle=math.radians(-55)+2*math.pi*t; target=Vector((0,0,30)); cam.data.ortho_scale=265; elevation=245
  cam.location=(420*math.cos(angle),420*math.sin(angle),elevation); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); cam.keyframe_insert(data_path='location',frame=f); cam.keyframe_insert(data_path='rotation_euler',frame=f)
 s.frame_start=1; s.frame_end=144; s.frame_set(1)
 bpy.ops.wm.save_as_mainfile(filepath=str(root/'enclosure/animation'/f'{clip}.blend'))
 frames=out/'frames'/clip; frames.mkdir(parents=True,exist_ok=True)
 for f in ([1,73] if a.preview else range(1,145)):
  s.frame_set(f); s.render.filepath=str(frames/f'{f:04}.png'); bpy.ops.render.render(write_still=True)
