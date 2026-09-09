"""Export the loaded enclosure scene with a merged timeline and metre units."""
import bpy, struct, json
from pathlib import Path
ROOT=Path(bpy.data.filepath).resolve().parents[1]
path=ROOT/'docs/vinyl_adc_assembled.glb'
bpy.ops.export_scene.gltf(filepath=str(path),use_selection=True,export_animations=True,export_yup=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name='Assembly')
raw=path.read_bytes(); size=struct.unpack_from('<I',raw,12)[0]
data=json.loads(raw[20:20+size]); rest=raw[20+size:]
# Blender's glTF exporter exports numeric millimetre coordinates unchanged.
# Put a static unit-conversion node above all roots, preserving animations.
for scene in data['scenes']:
 index=len(data['nodes'])
 data['nodes'].append({'name':'Millimetres to metres','scale':[0.001]*3,'children':scene['nodes']})
 scene['nodes']=[index]
assert len(data['animations'])==1 and data['animations'][0]['name']=='Assembly'
encoded=json.dumps(data,separators=(',',':')).encode(); encoded+=b' '*((-len(encoded))%4)
path.write_bytes(struct.pack('<III',0x46546c67,2,20+len(encoded)+len(rest))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+rest)
(ROOT/'media/vinyl_adc_assembled.glb').write_bytes(path.read_bytes())
