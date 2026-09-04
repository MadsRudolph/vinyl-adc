import bpy
import math
import os
from mathutils import Vector, Euler

# =============================================================================
# Configuration & Output Paths
# =============================================================================
REPO_DIR = r"C:\Users\Mads2\vinyl-adc"
RENDER_DIR = os.path.join(REPO_DIR, "render")
os.makedirs(RENDER_DIR, exist_ok=True)

HERO_PNG = os.path.join(RENDER_DIR, "vinyl-adc-hero.png")
FRONT_PNG = os.path.join(RENDER_DIR, "vinyl-adc-front.png")
EXPLODED_PNG = os.path.join(RENDER_DIR, "vinyl-adc-exploded.png")
BLEND_OUT = os.path.join(RENDER_DIR, "vinyl_adc_render.blend")

scene = bpy.context.scene

# =============================================================================
# Render Engine & Quality Settings
# =============================================================================
# Set 1920x1080 resolution
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '8'
scene.render.image_settings.compression = 15

# Use Eevee / Cycles
# Blender 5.1 / 4.x EEVEE-Next
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
except:
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except:
        scene.render.engine = 'CYCLES'

# Eevee quality properties if available
if hasattr(scene, 'eevee'):
    eevee = scene.eevee
    if hasattr(eevee, 'use_gtao'): eevee.use_gtao = True
    if hasattr(eevee, 'use_bloom'): eevee.use_bloom = True
    if hasattr(eevee, 'use_ssr'): eevee.use_ssr = True
    if hasattr(eevee, 'shadow_cascade_size'): eevee.shadow_cascade_size = '2048'

# World background: neutral warm studio grey
world = scene.world
if world and world.use_nodes:
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[0].default_value = (0.06, 0.065, 0.075, 1.0)
        bg_node.inputs[1].default_value = 1.0

# =============================================================================
# Studio Lighting Setup
# =============================================================================
# Remove existing lights to ensure clean controlled studio lighting
for obj in list(scene.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)

def add_light(name, light_type, loc, rot, energy, size=1.0, color=(1.0, 1.0, 1.0)):
    light_data = bpy.data.lights.new(name=name, type=light_type)
    light_data.energy = energy
    light_data.color = color
    if light_type == 'AREA':
        light_data.size = size
    obj = bpy.data.objects.new(name=name, object_data=light_data)
    obj.location = loc
    obj.rotation_euler = rot
    scene.collection.objects.link(obj)
    return obj

# 1. Key Light (Soft, warm, top-front-right)
add_light("Studio_Key_Light", 'AREA', 
          loc=(200.0, -220.0, 260.0), 
          rot=(math.radians(48.0), math.radians(15.0), math.radians(40.0)), 
          energy=1800.0, size=220.0, color=(1.0, 0.98, 0.95))

# 2. Fill Light (Soft, cool, front-left)
add_light("Studio_Fill_Light", 'AREA', 
          loc=(-240.0, -180.0, 180.0), 
          rot=(math.radians(52.0), math.radians(-18.0), math.radians(-50.0)), 
          energy=900.0, size=280.0, color=(0.92, 0.95, 1.0))

# 3. Rim / Accent Light (Rear top backlight to edge connectors & lid)
add_light("Studio_Rim_Light", 'AREA', 
          loc=(120.0, 260.0, 280.0), 
          rot=(math.radians(-55.0), math.radians(10.0), math.radians(-160.0)), 
          energy=1200.0, size=200.0, color=(1.0, 1.0, 1.0))

# 4. Top Down Overhead Soft Light
add_light("Studio_Top_Light", 'AREA', 
          loc=(0.0, 0.0, 320.0), 
          rot=(0.0, 0.0, 0.0), 
          energy=700.0, size=350.0, color=(0.98, 0.98, 1.0))

# =============================================================================
# Camera Setup
# =============================================================================
cam_obj = bpy.data.objects.get("Camera")
if not cam_obj:
    cam_data = bpy.data.cameras.new("Camera")
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.data.lens = 70.0 # 70 mm portrait / studio lens for distortion-free renders
cam_obj.data.clip_start = 1.0
cam_obj.data.clip_end = 2000.0

# Ensure lid has crystal clear acrylic material
lid = bpy.data.objects.get("Plexiglass_Clear_Lid")
if lid and lid.data.materials:
    mat = lid.data.materials[0]
    if mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Clear glass / acrylic: Transmission = 1.0, Roughness = 0.05, IOR = 1.49
            if "Transmission Weight" in bsdf.inputs:
                bsdf.inputs["Transmission Weight"].default_value = 0.95
            elif "Transmission" in bsdf.inputs:
                bsdf.inputs["Transmission"].default_value = 0.95
            bsdf.inputs["Roughness"].default_value = 0.04
            bsdf.inputs["IOR"].default_value = 1.49
            bsdf.inputs["Base Color"].default_value = (0.95, 0.98, 1.0, 1.0)
            if hasattr(mat, "blend_method"):
                mat.blend_method = 'BLEND'
            if hasattr(mat, "shadow_method"):
                mat.shadow_method = 'NONE'

# Ensure base has matte PLA finish
base = bpy.data.objects.get("Enclosure_3D_Print_Base")
if base and base.data.materials:
    mat = base.data.materials[0]
    if mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Matte dark charcoal PLA
            bsdf.inputs["Base Color"].default_value = (0.04, 0.042, 0.048, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.48

# Store original positions of objects for clean resets
original_locs = {}
for obj in bpy.data.objects:
    original_locs[obj.name] = Vector(obj.location)

def reset_positions():
    for name, loc in original_locs.items():
        obj = bpy.data.objects.get(name)
        if obj:
            obj.location = Vector(loc)

# =============================================================================
# 1. HERO SHOT (3/4 Isometric / Perspective View)
# =============================================================================
reset_positions()
# Position camera at 3/4 perspective: looking at front and right connector wall
cam_obj.location = Vector((270.0, -320.0, 220.0))
# Look at center of enclosure (X=0, Y=0, Z=35.0)
direction = Vector((0.0, 0.0, 32.0)) - cam_obj.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

scene.render.filepath = HERO_PNG
print(f"Rendering Hero Shot to {HERO_PNG}...")
bpy.ops.render.render(write_still=True)
print("Hero Shot Done.")

# =============================================================================
# 2. FRONT / CONNECTOR PANEL VIEW
# =============================================================================
reset_positions()
# Elevated front-angle shot: highlights front trim knob, badge, and side RCA jacks
cam_obj.location = Vector((180.0, -360.0, 130.0))
direction = Vector((15.0, 0.0, 32.0)) - cam_obj.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

scene.render.filepath = FRONT_PNG
print(f"Rendering Front-Panel Shot to {FRONT_PNG}...")
bpy.ops.render.render(write_still=True)
print("Front-Panel Shot Done.")

# =============================================================================
# 3. EXPLODED VIEW (Lid Lifted, PCB Tiers Staggered)
# =============================================================================
reset_positions()

# Explode elements upward along Z to show the 4 PCB tiers and interior
# 1. Lid lifted way up
if lid:
    lid.location.z += 95.0

# 2. Lid screws lifted above lid
for i in range(1, 5):
    for prefix in ["M3_Lid_Screw_Head_", "M3_Lid_Screw_Shaft_"]:
        s = bpy.data.objects.get(f"{prefix}{i}")
        if s: s.location.z += 105.0

# 3. Digital Board (Tier 4) lifted
pcb4 = bpy.data.objects.get("Real_PCB_4_Digital_Root")
if pcb4: pcb4.location.z += 50.0

# Top standoffs and nuts lifted with Tier 4
for i in range(1, 5):
    for prefix in ["M3_PCB_Top_Nut_", "Standoff_Tier3_11mm_"]:
        s = bpy.data.objects.get(f"{prefix}{i}")
        if s: s.location.z += 50.0

# Pi ribbon socket lifted
pi_sock = bpy.data.objects.get("Pi_IDC_Socket")
if pi_sock: pi_sock.location.z += 50.0
pi_rib = bpy.data.objects.get("Pi_Ribbon_Cable")
if pi_rib: pi_rib.location.z += 50.0

# 4. Channel L (Tier 3) lifted
pcb3 = bpy.data.objects.get("Real_PCB_3_Channel_L_Root")
if pcb3: pcb3.location.z += 30.0
for i in range(1, 5):
    s = bpy.data.objects.get(f"Standoff_Tier2_11mm_{i}")
    if s: s.location.z += 30.0

# 5. Channel R (Tier 2) lifted slightly
pcb2 = bpy.data.objects.get("Real_PCB_2_Channel_R_Root")
if pcb2: pcb2.location.z += 12.0
for i in range(1, 5):
    s = bpy.data.objects.get(f"Standoff_Tier1_11mm_{i}")
    if s: s.location.z += 12.0

# Camera for exploded view: wider angle, higher perspective
cam_obj.location = Vector((300.0, -340.0, 280.0))
direction = Vector((0.0, 0.0, 60.0)) - cam_obj.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

scene.render.filepath = EXPLODED_PNG
print(f"Rendering Exploded Shot to {EXPLODED_PNG}...")
bpy.ops.render.render(write_still=True)
print("Exploded Shot Done.")

# Reset positions before saving blend file
reset_positions()

# Save final reproducible .blend file
bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print(f"Saved blend file to {BLEND_OUT}")
print("All renders complete!")
