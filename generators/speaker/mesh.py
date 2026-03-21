"""Speaker mesh construction — PA/DJ cabinet with woofer, tweeter, and hardware.

Builds a low-poly speaker (300-500 faces) with:
  - Rectangular cabinet body (black, high-roughness)
  - Speaker grille covering the front face
  - Woofer cone (concentric ring pattern, slight Z depression)
  - Tweeter dome (small hemisphere, floor_standing / wall_mount only)
  - Corner protector hardware at all 8 cabinet corners
  - Carry handle on top (floor_standing only)
  - Wall bracket plate on the back (wall_mount only)

Origin is at the bottom-center of the cabinet (feet at Z=0).
Cabinet front face is at +Y, rear at -Y.
"""

import bpy
import bmesh
import math
from mathutils import Vector

from generators.base import BaseAssetGenerator

# Bind base utilities as module-level names for clean call sites
_clear_scene = BaseAssetGenerator._clear_scene
_join = BaseAssetGenerator._join
_finalize = BaseAssetGenerator._finalize
_apply_material = BaseAssetGenerator._apply_material


# ---------------------------------------------------------------------------
# Material color constants
# ---------------------------------------------------------------------------

CABINET_COLOR   = (0.08, 0.08, 0.08, 1.0)
GRILLE_COLOR    = (0.05, 0.05, 0.05, 1.0)
WOOFER_COLOR    = (0.12, 0.12, 0.12, 1.0)
TWEETER_COLOR   = (0.15, 0.15, 0.15, 1.0)
HARDWARE_COLOR  = (0.60, 0.60, 0.65, 1.0)
HANDLE_COLOR    = (0.55, 0.55, 0.60, 1.0)
BRACKET_COLOR   = (0.50, 0.50, 0.55, 1.0)


# ---------------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------------

def _build_cabinet(cfg, style):
    """Rectangular box forming the main speaker cabinet body."""
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, h / 2))
    cab = bpy.context.active_object
    cab.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    cab.name = "Speaker_Cabinet"

    # EdgeSplit for hard-cornered look
    mod = cab.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(30)

    _apply_material(
        cab, style, "Mat_Cabinet",
        color=CABINET_COLOR,
        roughness=0.85,
        metallic=0.0,
    )
    return cab


def _build_grille(cfg, style):
    """Flat plane covering the front face of the cabinet, slightly inset."""
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]

    # Inset 1 mm inside the front face
    front_y = d / 2 - 0.01
    grille_w = w * 0.92
    grille_h = h * 0.88

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, front_y, h / 2))
    grille = bpy.context.active_object
    grille.scale = (grille_w, grille_h, 1.0)
    grille.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    grille.name = "Speaker_Grille"

    _apply_material(
        grille, style, "Mat_Grille",
        color=GRILLE_COLOR,
        roughness=0.9,
        metallic=0.5,
    )
    return grille


def _build_woofer(cfg, style):
    """Woofer cone — concentric rings with slight Z-depression simulating cone shape."""
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]
    woofer_r = cfg["woofer_radius"]
    variation = cfg.get("variation", "floor_standing")

    # For floor_standing/wall_mount: center lower half; for subwoofer: center of face
    if variation == "subwoofer":
        center_z = h / 2
    else:
        center_z = h * 0.32   # lower third of the face

    front_y = d / 2

    bm = bmesh.new()

    # Build concentric rings: 4 rings from outer to inner with slight depression
    num_rings = 4
    ring_verts = 16   # vertices per ring
    cone_depth = woofer_r * 0.18   # maximum depression at center

    ring_radii = [woofer_r * (1.0 - i / num_rings) for i in range(num_rings + 1)]
    all_ring_loops = []

    for ri, radius in enumerate(ring_radii):
        # Z depression increases toward center (ring index increases inward)
        z_offset = -(cone_depth * (ri / num_rings) ** 1.5)
        ring = []
        for vi in range(ring_verts):
            angle = 2 * math.pi * vi / ring_verts
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            # Y is the "depth" direction; cone pushes inward (negative Y = toward rear)
            y = front_y + z_offset
            v = bm.verts.new(Vector((x, y, z + center_z)))
            ring.append(v)
        all_ring_loops.append(ring)

    # Fill faces between consecutive rings
    for ri in range(num_rings):
        outer = all_ring_loops[ri]
        inner = all_ring_loops[ri + 1]
        for vi in range(ring_verts):
            vi_next = (vi + 1) % ring_verts
            try:
                bm.faces.new([
                    outer[vi], outer[vi_next],
                    inner[vi_next], inner[vi],
                ])
            except ValueError:
                pass

    # Cap center with a flat disc polygon
    center_ring = all_ring_loops[-1]
    try:
        bm.faces.new(center_ring)
    except ValueError:
        pass

    mesh_data = bpy.data.meshes.new("Speaker_Woofer_Mesh")
    bm.to_mesh(mesh_data)
    bm.free()

    woofer = bpy.data.objects.new("Speaker_Woofer", mesh_data)
    bpy.context.collection.objects.link(woofer)
    bpy.context.view_layer.objects.active = woofer

    _apply_material(
        woofer, style, "Mat_Woofer",
        color=WOOFER_COLOR,
        roughness=0.95,
        metallic=0.1,
    )
    return woofer


def _build_tweeter(cfg, style):
    """Small hemisphere representing the tweeter dome at upper-center of front face."""
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]
    tweeter_r = cfg["tweeter_radius"]

    center_z = h * 0.72   # upper portion of face
    front_y = d / 2

    bm = bmesh.new()

    # Build a hemisphere (upper half of a UV sphere)
    lat_steps = 5
    lon_steps = 10
    dome_verts = []

    for lat in range(lat_steps + 1):
        lat_angle = math.pi / 2 * (lat / lat_steps)   # 0 to pi/2
        ring = []
        for lon in range(lon_steps):
            lon_angle = 2 * math.pi * lon / lon_steps
            x = tweeter_r * math.cos(lat_angle) * math.cos(lon_angle)
            z = tweeter_r * math.cos(lat_angle) * math.sin(lon_angle)
            y = front_y + tweeter_r * math.sin(lat_angle)
            v = bm.verts.new(Vector((x, y, z + center_z)))
            ring.append(v)
        dome_verts.append(ring)

    # Fill quad faces between latitude rings
    for lat in range(lat_steps):
        lower = dome_verts[lat]
        upper = dome_verts[lat + 1]
        for lon in range(lon_steps):
            lon_next = (lon + 1) % lon_steps
            try:
                bm.faces.new([
                    lower[lon], lower[lon_next],
                    upper[lon_next], upper[lon],
                ])
            except ValueError:
                pass

    # Cap the dome tip (top latitude ring forms a small polygon)
    try:
        bm.faces.new(dome_verts[-1])
    except ValueError:
        pass

    # Base disc to close the hemisphere
    base_ring = dome_verts[0]
    try:
        bm.faces.new(list(reversed(base_ring)))
    except ValueError:
        pass

    mesh_data = bpy.data.meshes.new("Speaker_Tweeter_Mesh")
    bm.to_mesh(mesh_data)
    bm.free()

    tweeter = bpy.data.objects.new("Speaker_Tweeter", mesh_data)
    bpy.context.collection.objects.link(tweeter)
    bpy.context.view_layer.objects.active = tweeter

    _apply_material(
        tweeter, style, "Mat_Tweeter",
        color=TWEETER_COLOR,
        roughness=0.8,
        metallic=0.2,
    )
    return tweeter


def _build_corner_hardware(cfg, style):
    """8 small metal cube corner protectors at the 8 corners of the cabinet."""
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]

    corner_size = 0.025   # 2.5 cm metal corner cube

    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (0, 1):
                cx = sx * (w / 2 - corner_size / 2)
                cy = sy * (d / 2 - corner_size / 2)
                cz = sz * h + (-corner_size / 2 if sz == 1 else corner_size / 2)

                bpy.ops.mesh.primitive_cube_add(
                    size=corner_size,
                    location=(cx, cy, cz),
                )
                corner = bpy.context.active_object
                corner.name = "Speaker_Corner"

                _apply_material(
                    corner, style, "Mat_CornerHardware",
                    color=HARDWARE_COLOR,
                    roughness=0.3,
                    metallic=0.9,
                )
                corners.append(corner)

    return corners


def _build_handle(cfg, style):
    """Carry handle on the top face: two vertical posts + one horizontal bar."""
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]

    handle_r = 0.012       # cylinder radius
    post_height = 0.055    # how tall each vertical post is
    span = w * 0.35        # distance between posts (centered on top)
    bar_len = span         # horizontal bar length

    parts = []

    # Two vertical posts
    for side in (-1, 1):
        px = side * span / 2
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8,
            radius=handle_r,
            depth=post_height,
            location=(px, 0, h + post_height / 2),
        )
        post = bpy.context.active_object
        post.name = "Speaker_HandlePost"
        _apply_material(
            post, style, "Mat_Handle",
            color=HANDLE_COLOR,
            roughness=0.3,
            metallic=0.9,
        )
        parts.append(post)

    # Horizontal bar connecting the tops of both posts
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=handle_r,
        depth=bar_len,
        location=(0, 0, h + post_height),
        rotation=(0, math.radians(90), 0),
    )
    bar = bpy.context.active_object
    bar.name = "Speaker_HandleBar"
    _apply_material(
        bar, style, "Mat_HandleBar",
        color=HANDLE_COLOR,
        roughness=0.3,
        metallic=0.9,
    )
    parts.append(bar)

    return _join(parts, "Speaker_Handle")


def _build_wall_bracket(cfg, style):
    """Wall bracket plate on the rear face of a wall-mount speaker.

    A flat plate with two small cylinder stubs to imply mounting bolt holes.
    """
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]

    plate_w = w * 0.65
    plate_h = h * 0.40
    plate_t = 0.015
    rear_y = -(d / 2 + plate_t / 2)
    center_z = h / 2

    # Bracket back plate
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, rear_y, center_z))
    plate = bpy.context.active_object
    plate.scale = (plate_w, plate_t, plate_h)
    bpy.ops.object.transform_apply(scale=True)
    plate.name = "Speaker_BracketPlate"
    _apply_material(
        plate, style, "Mat_Bracket",
        color=BRACKET_COLOR,
        roughness=0.4,
        metallic=0.85,
    )

    parts = [plate]

    # Mounting bolt stubs (small cylinders)
    bolt_r = 0.008
    bolt_depth = 0.02
    for bx in (-plate_w * 0.35, plate_w * 0.35):
        for bz in (center_z - plate_h * 0.3, center_z + plate_h * 0.3):
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=6,
                radius=bolt_r,
                depth=bolt_depth,
                location=(bx, rear_y - bolt_depth / 2, bz),
                rotation=(math.radians(90), 0, 0),
            )
            bolt = bpy.context.active_object
            bolt.name = "Speaker_BracketBolt"
            _apply_material(
                bolt, style, "Mat_BracketBolt",
                color=HARDWARE_COLOR,
                roughness=0.25,
                metallic=1.0,
            )
            parts.append(bolt)

    return _join(parts, "Speaker_WallBracket")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def create_speaker(cfg, style):
    """Build a speaker cabinet asset from config and style.

    Args:
        cfg: dict with keys: width, height, depth, woofer_radius,
             tweeter_radius, corner_radius, variation.
        style: AssetStyle instance.

    Returns:
        The joined, finalized Blender object named "Speaker".
    """
    _clear_scene()

    parts = []

    cabinet = _build_cabinet(cfg, style)
    parts.append(cabinet)

    grille = _build_grille(cfg, style)
    parts.append(grille)

    woofer = _build_woofer(cfg, style)
    parts.append(woofer)

    variation = cfg.get("variation", "floor_standing")

    if variation != "subwoofer":
        tweeter = _build_tweeter(cfg, style)
        parts.append(tweeter)

    corners = _build_corner_hardware(cfg, style)
    parts.extend(corners)

    if variation == "floor_standing":
        handle = _build_handle(cfg, style)
        parts.append(handle)
    elif variation == "wall_mount":
        bracket = _build_wall_bracket(cfg, style)
        parts.append(bracket)

    result = _join(parts, "Speaker")
    return _finalize(result, "Speaker")
