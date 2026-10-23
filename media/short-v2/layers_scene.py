"""The four copper layers of rev D pulling apart, for the short (1080x1920, 30 fps, Cycles).

    tools/capped blender -b --factory-startup --python media/short-v2/layers_scene.py -- [--preview]

Layer art: kicad-cli SVG exports of F.Cu / In1.Cu / In2.Cu / B.Cu rasterised to layers/*.png (copper = opaque).
Frames go to build/layers/NNNN.png.
"""
import bpy,sys,math
from pathlib import Path
from mathutils import Vector

HERE=Path(__file__).resolve().parent;OUT=HERE/'build/layers';OUT.mkdir(parents=True,exist_ok=True)
FONT=HERE.parent/'rev-d-photos/fonts/Poppins-Bold.ttf';MONO=HERE.parent/'rev-d-photos/fonts/PlexMono-Medium.ttf'
pv='--preview' in sys.argv
W,D=0.140,0.136;N=150
LAYERS=[('F.Cu','Top: signals'),('In1.Cu','Solid ground plane'),('In2.Cu','+5 V and +5 VA power'),('B.Cu','Bottom: signals')]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene

def mat_copper(img):
    m=bpy.data.materials.new('cu_'+img);m.use_nodes=True;nt=m.node_tree;b=nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(.88,.45,.24,1);b.inputs['Metallic'].default_value=1;b.inputs['Roughness'].default_value=.3
    b.inputs['Emission Color'].default_value=(1,.45,.2,1);b.inputs['Emission Strength'].default_value=.35
    t=nt.nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.load(str(HERE/'layers'/f'{img}.png'));t.interpolation='Cubic'
    nt.links.new(t.outputs['Alpha'],b.inputs['Alpha'])
    return m

def mat_core():
    m=bpy.data.materials.new('core');m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(.010,.045,.022,1);b.inputs['Roughness'].default_value=.25;b.inputs['Coat Weight'].default_value=.6
    b.inputs['Transmission Weight'].default_value=.0;b.inputs['Alpha'].default_value=.78
    return m

def plane(name,z,mat,th=0.0):
    if th:
        bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,z));o=bpy.context.object;o.scale=(W,D,th)
    else:
        bpy.ops.mesh.primitive_plane_add(size=1,location=(0,0,z));o=bpy.context.object;o.scale=(W,D,1)
    o.name=name;o.data.materials.append(mat);return o

def text(body,font,size,loc,col,em=2.):
    c=bpy.data.curves.new('t','FONT');c.body=body;c.font=bpy.data.fonts.load(str(font));c.size=size;c.align_x='LEFT';c.align_y='CENTER'
    o=bpy.data.objects.new('t',c);sc.collection.objects.link(o);o.location=loc
    m=bpy.data.materials.new('txt');m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*col,1);b.inputs['Emission Color'].default_value=(*col,1);b.inputs['Emission Strength'].default_value=em
    c.materials.append(m);return o

pivot=bpy.data.objects.new('pivot',None);sc.collection.objects.link(pivot)
pivot.rotation_euler=(0,0,math.radians(-28))
cu=[];cores=[];labels=[]
for i,(img,label) in enumerate(LAYERS):
    o=plane(img,0,mat_copper(img));o.parent=pivot;cu.append(o)
    t=text(label,FONT,.0125,(W/2+.008,-D/2+.012,0),(1,1,1) if i!=1 else (.55,1,.65));t.parent=pivot;t.rotation_euler=(math.radians(62),0,0);labels.append(t)
    c=plane(f'sub{i}',0,mat_core(),th=.0008);c.parent=pivot;cores.append(c)

def smooth(u):u=min(1,max(0,u));return u*u*(3-2*u)
GAP=.03
for f in range(1,N+1):
    u=smooth((f-20)/50)                                # 0.7 s assembled, 1.7 s apart, then hold
    for i,o in enumerate(cu):
        z=(1.5-i)*(.0004+GAP*u);o.location.z=z;o.keyframe_insert('location',frame=f)
        t=labels[i];t.location.z=z;s=smooth((f-55-8*i)/14);t.scale=(s,s,s)
        t.keyframe_insert('location',frame=f);t.keyframe_insert('scale',frame=f)
    for i,c in enumerate(cores):
        c.location.z=cu[i].location.z-.00055;c.keyframe_insert('location',frame=f)
    pivot.rotation_euler.z=math.radians(-34+16*f/N);pivot.keyframe_insert('rotation_euler',frame=f)

# studio
w=bpy.data.worlds.new('w');sc.world=w;w.use_nodes=True;bg=w.node_tree.nodes['Background'];bg.inputs['Color'].default_value=(.006,.007,.009,1)
def area(name,loc,energy,size,col=(1,1,1)):
    l=bpy.data.lights.new(name,'AREA');l.energy=energy;l.size=size;l.color=col
    o=bpy.data.objects.new(name,l);sc.collection.objects.link(o);o.location=loc
    o.rotation_euler=(Vector((0,0,0))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
area('key',(-.35,-.25,.45),9,.5,(1,.93,.85));area('rim',(.35,.45,.2),8,.3,(.7,.85,1));area('fill',(.4,-.4,.1),1.5,.6)
cam=bpy.data.cameras.new('cam');co=bpy.data.objects.new('cam',cam);sc.collection.objects.link(co);sc.camera=co
cam.lens=31;cam.sensor_width=36;co.location=(.02,-.30,.25)
co.rotation_euler=(Vector((0.028,0,-.006))-co.location).to_track_quat('-Z','Y').to_euler()
cam.dof.use_dof=True;cam.dof.aperture_fstop=5.6;cam.dof.focus_distance=(co.location-Vector((0,0,0))).length

sc.render.engine='CYCLES';prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
sc.cycles.device='GPU';sc.cycles.samples=48 if not pv else 16;sc.cycles.use_denoising=True
sc.render.resolution_x,sc.render.resolution_y=1080,1920;sc.render.fps=30
sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Punchy'
sc.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'build/layers.blend'))
for f in ((1,45,70,110,150) if pv else range(1,N+1)):
    p=OUT/(f'preview-{f:04}.png' if pv else f'{f:04}.png')
    if p.exists() and not pv:continue
    sc.frame_set(f);sc.render.filepath=str(p);bpy.ops.render.render(write_still=True)
