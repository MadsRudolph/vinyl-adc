"""Build a small labelled fit coupon before committing to the enclosure print.
Run: blender --factory-startup -b -noaudio --python enclosure/build_insert_coupon.py
"""
from pathlib import Path
import bpy, bmesh

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1, location=(24, 8, 4.5))
base=bpy.context.object
base.name='M3 insert pilot fit coupon (mm)'
base.dimensions=(48,16,9)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)

def subtract(cutter):
 bpy.context.view_layer.objects.active=base
 mod=base.modifiers.new('Cut','BOOLEAN'); mod.object=cutter; mod.solver='EXACT'
 bpy.ops.object.modifier_apply(modifier=mod.name)
 bpy.data.objects.remove(cutter,do_unlink=True)

for x,d in zip((7,18,29,40),(4.0,4.2,4.4,4.6)):
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=d/2,depth=7,location=(x,10,6))
 subtract(bpy.context.object)
 bpy.ops.object.text_add(location=(x-2.8,2,8.5))
 text=bpy.context.object; text.data.body=f'{d:.1f}'; text.data.size=3.2; text.data.extrude=0.8
 bpy.ops.object.convert(target='MESH'); subtract(bpy.context.object)
bpy.ops.object.select_all(action='DESELECT'); base.select_set(True)
bpy.context.view_layer.objects.active=base
bm=bmesh.new(); bm.from_mesh(base.data)
assert all(e.is_manifold for e in bm.edges)
bm.free()
bpy.ops.wm.stl_export(filepath=str(Path(__file__).with_name('m3_insert_fit_coupon.stl')),export_selected_objects=True)
