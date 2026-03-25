"""Quick preview render: generate the humanoid and save a PNG.

Usage (run from repo root):
    blender --background --python scripts/preview_humanoid.py

Output:
    assets/preview.png   — front + 3/4 view composite, 800 × 400 px

No extra arguments needed.  The script calls the same generator as
generate_humanoid.py so it always reflects the latest code.
"""

import sys
import os
import math

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import bpy
from mathutils import Vector

# ── 1. Generate the character ──────────────────────────────────────────────────
from generators.humanoid import generate

cfg_overrides = {
    "preset":     "average",
    "gender":     "male",
    "skin_tone":  "medium",
    "hair_style": "short",
    "hair_color": "dark_brown",
    "animations": [],
}

generate(cfg_overrides)   # populates the scene

# ── 2. Camera + lighting ───────────────────────────────────────────────────────

def _add_camera(name, location, look_at=(0, 0, 0.9)):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    cam.name = name
    # Point at look_at
    direction = Vector(look_at) - Vector(location)
    rot_quat  = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    cam.data.lens = 50
    return cam


def _add_sun(location, energy=3.0):
    bpy.ops.object.light_add(type='SUN', location=location)
    sun = bpy.context.active_object
    sun.data.energy = energy
    sun.rotation_euler = (math.radians(45), 0, math.radians(30))
    return sun


# Remove default camera/light if present
for obj in list(bpy.data.objects):
    if obj.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(obj, do_unlink=True)

_add_sun((5, -5, 10))

cam_front   = _add_camera("Cam_Front",   (0,  -3.5, 1.0),   look_at=(0, 0, 0.9))
cam_quarter = _add_camera("Cam_Quarter", (2.5, -2.5, 1.3),  look_at=(0, 0, 0.9))

# ── 3. Render settings ─────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine         = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'EEVEE_NEXT') else 'BLENDER_EEVEE'
scene.render.film_transparent = False
scene.render.resolution_x   = 400
scene.render.resolution_y   = 400
scene.render.image_settings.file_format = 'PNG'

out_dir = os.path.join(project_root, "assets")
os.makedirs(out_dir, exist_ok=True)

# ── 4. Render front view ───────────────────────────────────────────────────────
scene.camera = cam_front
front_path   = os.path.join(out_dir, "_preview_front.png")
scene.render.filepath = front_path
bpy.ops.render.render(write_still=True)

# ── 5. Render 3/4 view ────────────────────────────────────────────────────────
scene.camera = cam_quarter
quarter_path = os.path.join(out_dir, "_preview_quarter.png")
scene.render.filepath = quarter_path
bpy.ops.render.render(write_still=True)

# ── 6. Composite side-by-side ─────────────────────────────────────────────────
try:
    from PIL import Image
    img_front   = Image.open(front_path)
    img_quarter = Image.open(quarter_path)
    composite = Image.new("RGB", (800, 400))
    composite.paste(img_front,   (0,   0))
    composite.paste(img_quarter, (400, 0))
    composite_path = os.path.join(out_dir, "preview.png")
    composite.save(composite_path)
    os.remove(front_path)
    os.remove(quarter_path)
    print(f"[preview] Saved composite → {composite_path}")
except ImportError:
    # PIL not available: just rename front view
    import shutil
    composite_path = os.path.join(out_dir, "preview.png")
    shutil.move(front_path, composite_path)
    print(f"[preview] PIL not available; saved front view → {composite_path}")
    print(f"[preview] 3/4 view saved separately → {quarter_path}")

print("[preview] Done.")
