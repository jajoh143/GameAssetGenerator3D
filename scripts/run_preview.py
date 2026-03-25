"""Wrapper script to run preview from Blender's text editor.
Sets up sys.path correctly before importing generators.
"""
import sys
import os

# Force the project root into sys.path
PROJECT_ROOT = '/Users/jjohnson/GameAssetGenerator3D'
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now we can import and run the generator
import bpy
import math
from mathutils import Vector, Color

from generators.humanoid import generate

# ── 1. Clear the scene ──────────────────────────────────────────────
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

# ── 2. Generate the character ───────────────────────────────────────
cfg_overrides = {
    "preset":     "average",
    "gender":     "male",
    "skin_tone":  "medium",
    "hair_style": "spiky",
    "hair_color": "dark_brown",
    "clothing":   ["tshirt", "pants"],
    "clothing_color": None,
    "animations": [],
}

generate(cfg_overrides)

# ── 3. 3-point lighting ─────────────────────────────────────────────
def _add_camera(name, location, look_at=(0, 0, 0.85)):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    cam.name = name
    direction = Vector(look_at) - Vector(location)
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    cam.data.lens = 65  # slightly telephoto for flattering proportions
    return cam

# Key light — warm, strong, from upper-right
bpy.ops.object.light_add(type='SUN', location=(4, -3, 8))
key = bpy.context.active_object
key.name = "Key_Light"
key.data.energy = 5.5
key.data.color = (1.0, 0.94, 0.84)  # warm golden white
key.rotation_euler = (math.radians(40), 0, math.radians(25))

# Fill light — slightly warm, brighter for better shadow fill
bpy.ops.object.light_add(type='SUN', location=(-3, -4, 5))
fill = bpy.context.active_object
fill.name = "Fill_Light"
fill.data.energy = 2.0
fill.data.color = (0.88, 0.90, 1.0)  # cooler fill for contrast with warm key
fill.rotation_euler = (math.radians(55), 0, math.radians(-35))

# Rim light — from behind for edge definition
bpy.ops.object.light_add(type='SUN', location=(1, 4, 6))
rim = bpy.context.active_object
rim.name = "Rim_Light"
rim.data.energy = 3.0
rim.data.color = (1.0, 0.95, 0.88)
rim.rotation_euler = (math.radians(130), 0, math.radians(10))

# Cameras
cam_front   = _add_camera("Cam_Front",   (0, -3.2, 0.95),  look_at=(0, 0, 0.85))
cam_quarter = _add_camera("Cam_Quarter", (2.2, -2.3, 1.1), look_at=(0, 0, 0.85))

# ── 4. World background — soft gradient ─────────────────────────────
world = bpy.data.worlds.new("Preview_World")
bpy.context.scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
nodes.clear()

bg = nodes.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.0

# Gradient from warm grey-blue at bottom to lighter at top
coord = nodes.new('ShaderNodeTexCoord')
sep = nodes.new('ShaderNodeSeparateXYZ')
ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.28, 0.28, 0.32, 1.0)  # warmer dark grey
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[1].color = (0.55, 0.55, 0.58, 1.0)  # brighter warm grey
ramp.color_ramp.elements[1].position = 1.0

output = nodes.new('ShaderNodeOutputWorld')

links.new(coord.outputs['Window'], sep.inputs[0])
links.new(sep.outputs['Y'], ramp.inputs['Fac'])
links.new(ramp.outputs['Color'], bg.inputs['Color'])
links.new(bg.outputs['Background'], output.inputs['Surface'])

# ── 4b. Ground plane for shadow ────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground_Plane"
ground_mat = bpy.data.materials.new("Ground_Mat")
ground_mat.use_nodes = True
ground_bsdf = ground_mat.node_tree.nodes.get("Principled BSDF")
if ground_bsdf:
    ground_bsdf.inputs["Base Color"].default_value = (0.35, 0.35, 0.38, 1.0)
    ground_bsdf.inputs["Roughness"].default_value = 0.90
    ground_bsdf.inputs["Specular IOR Level"].default_value = 0.05
ground.data.materials.append(ground_mat)

# ── 5. Render settings ──────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.film_transparent = False
scene.render.resolution_x = 768
scene.render.resolution_y = 768
scene.render.image_settings.file_format = 'PNG'

out_dir = os.path.join(PROJECT_ROOT, "assets")
os.makedirs(out_dir, exist_ok=True)

# ── 6. Render front view ────────────────────────────────────────────
scene.camera = cam_front
front_path = os.path.join(out_dir, "_preview_front.png")
scene.render.filepath = front_path
bpy.ops.render.render(write_still=True)

# ── 7. Render 3/4 view ──────────────────────────────────────────────
scene.camera = cam_quarter
quarter_path = os.path.join(out_dir, "_preview_quarter.png")
scene.render.filepath = quarter_path
bpy.ops.render.render(write_still=True)

# ── 8. Composite ────────────────────────────────────────────────────
try:
    from PIL import Image
    img_front = Image.open(front_path)
    img_quarter = Image.open(quarter_path)
    composite = Image.new("RGB", (1024, 512))
    composite.paste(img_front, (0, 0))
    composite.paste(img_quarter, (512, 0))
    composite_path = os.path.join(out_dir, "preview.png")
    composite.save(composite_path)
    os.remove(front_path)
    os.remove(quarter_path)
    print(f"[preview] Saved composite → {composite_path}")
except ImportError:
    import shutil
    composite_path = os.path.join(out_dir, "preview.png")
    shutil.move(front_path, composite_path)
    print(f"[preview] PIL not available; saved front view → {composite_path}")
    print(f"[preview] 3/4 view saved separately → {quarter_path}")

print("[preview] Done.")
