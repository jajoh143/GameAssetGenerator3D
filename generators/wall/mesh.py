"""Wall mesh construction — 6 gritty urban variations.

Each builder creates low-poly geometry suitable for mobile games.
Walls are oriented along the X axis, with +Y as the "front face" normal.
Origin is at the bottom-center of the wall.
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector


def _clear_scene():
    """Remove default objects."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def _apply_material(obj, style, mat_name):
    """Apply a PBR material using the AssetStyle parameters."""
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = style.get_color()
        bsdf.inputs["Roughness"].default_value = style.get_roughness()
        bsdf.inputs["Metallic"].default_value = style.get_metallic()
    obj.data.materials.append(mat)


def _finalize(obj, style, variation):
    """Smooth normals + material + origin at base center."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    mod = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(30)
    _apply_material(obj, style, f"Wall_{variation}")
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return obj


# ---------------------------------------------------------------------------
# Variation builders
# ---------------------------------------------------------------------------

def _build_brick(cfg, style):
    """Brick wall — rows of offset bricks with mortar gaps."""
    w, h, d = cfg["width"], cfg["height"], cfg["depth"]

    brick_h = 0.075
    brick_w = 0.22
    mortar = 0.012
    row_h = brick_h + mortar

    rows = int(h / row_h)
    parts = []

    for row in range(rows):
        z = row * row_h + brick_h / 2
        offset = (brick_w / 2 + mortar / 2) if row % 2 else 0
        x = -w / 2 + offset + brick_w / 2

        while x + brick_w / 2 <= w / 2 + 0.01:
            # Clamp brick width at edges
            actual_w = min(brick_w, w / 2 - x + brick_w / 2)
            if actual_w < brick_w * 0.3:
                x += brick_w + mortar
                continue

            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, z))
            brick = bpy.context.active_object
            brick.scale = (actual_w, d, brick_h)
            bpy.ops.object.transform_apply(scale=True)

            # Slight random variation for grit
            if style.wear > 0.3:
                brick.location.x += random.uniform(-0.005, 0.005)
                brick.location.z += random.uniform(-0.003, 0.003)

            parts.append(brick)
            x += brick_w + mortar

    return _join(parts, "Wall_Brick")


def _build_concrete(cfg, style):
    """Concrete wall — single slab with panel line cuts."""
    w, h, d = cfg["width"], cfg["height"], cfg["depth"]

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, h / 2))
    slab = bpy.context.active_object
    slab.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    slab.name = "Wall_Concrete"

    # Add horizontal and vertical panel cuts via loop cuts (bmesh)
    bm = bmesh.new()
    bm.from_mesh(slab.data)

    # Subdivide the front face a few times for panel lines
    h_cuts = max(1, int(h / 1.2))
    w_cuts = max(1, int(w / 2.0))

    bmesh.ops.subdivide_edges(
        bm,
        edges=bm.edges[:],
        cuts=max(h_cuts, w_cuts),
        use_grid_fill=True,
    )

    # Wear: displace some verts slightly for a rough look
    if style.wear > 0.2:
        for v in bm.verts:
            if abs(v.co.y) > d / 2 - 0.01:  # front/back faces only
                v.co.y += random.uniform(-0.008, 0.008) * style.wear

    bm.to_mesh(slab.data)
    bm.free()

    return slab


def _build_corrugated(cfg, style):
    """Corrugated metal sheet — wavy profile along Z."""
    w, h, d = cfg["width"], cfg["height"], cfg["depth"]

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, h / 2))
    sheet = bpy.context.active_object
    sheet.scale = (w, 1, h)
    bpy.ops.object.transform_apply(scale=True)
    sheet.name = "Wall_Corrugated"

    # Subdivide for corrugation
    bm = bmesh.new()
    bm.from_mesh(sheet.data)

    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=int(w / 0.08),
                              use_grid_fill=True)

    wave_freq = 2 * math.pi / 0.15  # corrugation period
    wave_amp = d * 0.4

    for v in bm.verts:
        v.co.y = math.sin(v.co.x * wave_freq) * wave_amp

    # Wear: add random displacement
    if style.wear > 0.3:
        for v in bm.verts:
            v.co.y += random.uniform(-0.01, 0.01) * style.wear
            v.co.z += random.uniform(-0.005, 0.005) * style.wear

    bm.to_mesh(sheet.data)
    bm.free()

    # Solidify to give thickness
    mod = sheet.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = 0.005
    bpy.context.view_layer.objects.active = sheet
    bpy.ops.object.modifier_apply(modifier="Solidify")

    return sheet


def _build_plank(cfg, style):
    """Wooden plank wall — vertical boards with gaps."""
    w, h, d = cfg["width"], cfg["height"], cfg["depth"]

    plank_w = 0.18
    gap = 0.008
    parts = []

    x = -w / 2 + plank_w / 2
    while x < w / 2:
        actual_w = min(plank_w, w / 2 - x + plank_w / 2)
        if actual_w < 0.04:
            break

        # Random height variation for gritty look
        plank_h = h + random.uniform(-0.05, 0.05) * style.wear

        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, plank_h / 2))
        plank = bpy.context.active_object
        plank.scale = (actual_w, d, plank_h)
        bpy.ops.object.transform_apply(scale=True)

        # Wear: slight rotation/offset
        if style.wear > 0.3:
            plank.rotation_euler.z = random.uniform(-0.02, 0.02) * style.wear
            plank.location.y += random.uniform(-0.01, 0.01) * style.wear

        parts.append(plank)
        x += plank_w + gap

    return _join(parts, "Wall_Plank")


def _build_cinder(cfg, style):
    """Cinder block / CMU wall — large rectangular blocks."""
    w, h, d = cfg["width"], cfg["height"], cfg["depth"]

    block_w = 0.40
    block_h = 0.20
    mortar = 0.01
    row_h = block_h + mortar
    parts = []

    for row in range(int(h / row_h)):
        z = row * row_h + block_h / 2
        offset = (block_w / 2 + mortar / 2) if row % 2 else 0
        x = -w / 2 + offset + block_w / 2

        while x + block_w / 2 <= w / 2 + 0.01:
            actual_w = min(block_w, w / 2 - x + block_w / 2)
            if actual_w < block_w * 0.3:
                x += block_w + mortar
                continue

            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, z))
            block = bpy.context.active_object
            block.scale = (actual_w, d, block_h)
            bpy.ops.object.transform_apply(scale=True)

            if style.wear > 0.3:
                block.location.x += random.uniform(-0.005, 0.005)

            parts.append(block)
            x += block_w + mortar

    return _join(parts, "Wall_Cinder")


def _build_chainlink(cfg, style):
    """Chain-link fence — flat grid of diamond shapes.

    Uses a subdivided plane with faces removed in a diamond pattern
    to approximate the look at low poly. For actual transparency,
    an alpha-clip material would be used in-engine.
    """
    w, h, d = cfg["width"], cfg["height"], cfg["depth"]

    # Create a grid
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=int(w / 0.06),
        y_subdivisions=int(h / 0.06),
        size=1,
        location=(0, 0, h / 2),
    )
    grid = bpy.context.active_object
    grid.scale = (w, h, 1)
    grid.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    grid.name = "Wall_Chainlink"

    # Remove alternating faces for diamond pattern
    bm = bmesh.new()
    bm.from_mesh(grid.data)
    bm.faces.ensure_lookup_table()

    faces_to_delete = []
    for i, f in enumerate(bm.faces):
        cx = f.calc_center_median()
        # Checkerboard removal based on grid position
        ix = int((cx.x + w / 2) / 0.12)
        iz = int(cx.z / 0.12)
        if (ix + iz) % 2 == 0:
            faces_to_delete.append(f)

    bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

    # Wireframe-ify remaining mesh for fence look
    bm.to_mesh(grid.data)
    bm.free()

    # Wireframe modifier gives the links thickness
    mod = grid.modifiers.new(name="Wire", type='WIREFRAME')
    mod.thickness = 0.008
    bpy.context.view_layer.objects.active = grid
    bpy.ops.object.modifier_apply(modifier="Wire")

    # Add fence posts (simple cylinders at edges)
    parts = [grid]
    post_spacing = 2.0
    post_r = 0.025
    for px in _post_positions(w, post_spacing):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6, radius=post_r, depth=h,
            location=(px, 0, h / 2),
        )
        post = bpy.context.active_object
        parts.append(post)

    # Top rail
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=6, radius=post_r * 0.7, depth=w,
        location=(0, 0, h), rotation=(0, math.radians(90), 0),
    )
    parts.append(bpy.context.active_object)

    return _join(parts, "Wall_Chainlink")


def _post_positions(width, spacing):
    """Yield x positions for fence posts."""
    positions = [-width / 2, width / 2]
    x = -width / 2 + spacing
    while x < width / 2 - 0.1:
        positions.append(x)
        x += spacing
    return positions


def _join(parts, name):
    """Join objects into one mesh."""
    if not parts:
        bpy.ops.mesh.primitive_cube_add(size=0.01)
        return bpy.context.active_object

    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = name
    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

BUILDERS = {
    "brick": _build_brick,
    "concrete": _build_concrete,
    "corrugated": _build_corrugated,
    "plank": _build_plank,
    "cinder": _build_cinder,
    "chainlink": _build_chainlink,
}


def create_wall(cfg, variation, style):
    """Create a wall mesh of the given variation.

    Args:
        cfg: dict with 'width', 'height', 'depth'.
        variation: one of BUILDERS keys.
        style: AssetStyle instance.

    Returns:
        The wall Blender object.
    """
    _clear_scene()
    builder = BUILDERS[variation]
    wall = builder(cfg, style)
    wall = _finalize(wall, style, variation)
    return wall
