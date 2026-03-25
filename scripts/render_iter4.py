"""Iteration 4 render: 6-panel multi-angle view.

Panels:
  [0] Full body front
  [1] Full body 3/4
  [2] Head front close-up
  [3] Head side close-up  (checks hair circumference)
  [4] Head top-down       (checks crown coverage)
  [5] Full body back      (checks nape/back hair)
"""
import sys, os, math
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import bpy
from mathutils import Vector

from generators.humanoid import generate

generate({
    "preset":     "average",
    "gender":     "male",
    "skin_tone":  "medium",
    "hair_style": "short",
    "hair_color": "dark_brown",
    "animations": [],
})

# ── Camera helpers ────────────────────────────────────────────────────────────
def add_cam(name, loc, look_at=(0, 0, 0.9), lens=50):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.name = name
    d = Vector(look_at) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    return cam

def add_sun(loc, energy=3.5):
    bpy.ops.object.light_add(type='SUN', location=loc)
    s = bpy.context.active_object
    s.data.energy = energy
    s.rotation_euler = (math.radians(45), 0, math.radians(30))
    return s

# Remove default cam/light
for obj in list(bpy.data.objects):
    if obj.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(obj, do_unlink=True)

add_sun((5, -5, 10))
# Soft fill from other side
bpy.ops.object.light_add(type='SUN', location=(-4, -3, 7))
fill = bpy.context.active_object
fill.data.energy = 1.2
fill.rotation_euler = (math.radians(40), 0, math.radians(-40))

cams = {
    "front":    add_cam("C_Front",     ( 0.0, -3.5,  1.0), look_at=(0, 0, 0.90), lens=50),
    "quarter":  add_cam("C_Quarter",   ( 2.2, -2.8,  1.2), look_at=(0, 0, 0.90), lens=50),
    "head_f":   add_cam("C_HeadFront", ( 0.0, -2.0,  1.35), look_at=(0, 0, 1.35), lens=80),
    "head_s":   add_cam("C_HeadSide",  ( 2.2, -0.3,  1.35), look_at=(0, 0, 1.35), lens=80),
    "head_top": add_cam("C_HeadTop",   ( 0.0,  0.0,  2.20), look_at=(0, 0, 1.35), lens=80),
    "back":     add_cam("C_Back",      ( 0.0,  3.2,  1.0),  look_at=(0, 0, 0.90), lens=50),
}

# ── Render settings ───────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'EEVEE_NEXT') else 'BLENDER_EEVEE'
scene.render.film_transparent = False
scene.render.resolution_x = 400
scene.render.resolution_y = 400
scene.render.image_settings.file_format = 'PNG'

out_dir = os.path.join(project_root, "assets")
os.makedirs(out_dir, exist_ok=True)

tmp = {}
for key, cam in cams.items():
    scene.camera = cam
    p = os.path.join(out_dir, f"_it4_{key}.png")
    scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    tmp[key] = p
    print(f"[iter4] rendered {key} → {p}")

# ── Composite 2×3 grid ────────────────────────────────────────────────────────
try:
    from PIL import Image
    W, H = 400, 400
    order = ["front", "quarter", "head_f", "head_s", "head_top", "back"]
    grid = Image.new("RGB", (W * 3, H * 2))
    for idx, key in enumerate(order):
        row, col = divmod(idx, 3)
        img = Image.open(tmp[key])
        grid.paste(img, (col * W, row * H))
    out = os.path.join(out_dir, "preview_iter4.png")
    grid.save(out)
    for p in tmp.values():
        try: os.remove(p)
        except: pass
    print(f"[iter4] composite saved → {out}")
except ImportError:
    import shutil
    shutil.copy(tmp["front"], os.path.join(out_dir, "preview_iter4.png"))
    print("[iter4] PIL unavailable; saved front view only")

print("[iter4] Done.")
