"""Floor mesh construction — 6 gritty urban variations.

Each builder creates low-poly geometry suitable for mobile games.
Floors are on the XY plane with the top surface at Z=0 (so they
sit flush with the ground plane). Origin is at center.
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
    """Apply a PBR material using AssetStyle parameters."""
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = style.get_color()
        bsdf.inputs["Roughness"].default_value = style.get_roughness()
        bsdf.inputs["Metallic"].default_value = style.get_metallic()
    obj.data.materials.append(mat)


def _finalize(obj, style, variation):
    """Smooth normals + material + origin at center."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    mod = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(30)
    _apply_material(obj, style, f"Floor_{variation}")
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return obj


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
# Variation builders
# ---------------------------------------------------------------------------

def _build_concrete(cfg, style):
    """Poured concrete slab with crack-like edge detail."""
    w, l, d = cfg["width"], cfg["length"], cfg["depth"]

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -d / 2))
    slab = bpy.context.active_object
    slab.scale = (w, l, d)
    bpy.ops.object.transform_apply(scale=True)
    slab.name = "Floor_Concrete"

    # Subdivide top face for surface detail
    bm = bmesh.new()
    bm.from_mesh(slab.data)

    cuts = max(2, int(max(w, l) / 1.0))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts,
                              use_grid_fill=True)

    # Wear: displace top-surface verts for cracked / uneven look
    if style.wear > 0.2:
        for v in bm.verts:
            if v.co.z > -0.01:  # top surface
                v.co.z += random.uniform(-0.015, 0.005) * style.wear

    bm.to_mesh(slab.data)
    bm.free()
    return slab


def _build_metal_plate(cfg, style):
    """Industrial diamond-plate metal floor."""
    w, l, d = cfg["width"], cfg["length"], cfg["depth"]

    # Base plate
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -d / 2))
    plate = bpy.context.active_object
    plate.scale = (w, l, d)
    bpy.ops.object.transform_apply(scale=True)
    plate.name = "Floor_MetalPlate"

    parts = [plate]

    # Diamond pattern: raised bumps on surface
    bump_spacing = 0.15
    bump_size = 0.025
    bump_height = 0.008

    x = -w / 2 + bump_spacing / 2
    row = 0
    while x < w / 2:
        y_start = -l / 2 + bump_spacing / 2
        if row % 2:
            y_start += bump_spacing / 2
        y = y_start
        while y < l / 2:
            bpy.ops.mesh.primitive_cube_add(
                size=1,
                location=(x, y, bump_height / 2),
            )
            bump = bpy.context.active_object
            bump.scale = (bump_size, bump_size, bump_height)
            bump.rotation_euler.z = math.radians(45)
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            parts.append(bump)
            y += bump_spacing
        x += bump_spacing
        row += 1

    return _join(parts, "Floor_MetalPlate")


def _build_wood_plank(cfg, style):
    """Wooden plank flooring — parallel boards along Y axis."""
    w, l, d = cfg["width"], cfg["length"], cfg["depth"]

    plank_w = 0.15
    gap = 0.006
    parts = []

    x = -w / 2 + plank_w / 2
    while x < w / 2:
        actual_w = min(plank_w, w / 2 - x + plank_w / 2)
        if actual_w < 0.03:
            break

        # Slight length variation for grit
        plank_l = l + random.uniform(-0.03, 0.03) * style.wear

        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, -d / 2))
        plank = bpy.context.active_object
        plank.scale = (actual_w, plank_l, d)
        bpy.ops.object.transform_apply(scale=True)

        # Wear: warp individual planks slightly
        if style.wear > 0.3:
            plank.location.z += random.uniform(-0.005, 0.005) * style.wear
            plank.rotation_euler.x = random.uniform(-0.01, 0.01) * style.wear

        parts.append(plank)
        x += plank_w + gap

    return _join(parts, "Floor_WoodPlank")


def _build_tile(cfg, style):
    """Square tile floor with visible grout lines."""
    w, l, d = cfg["width"], cfg["length"], cfg["depth"]

    tile_size = 0.40
    grout = 0.01
    step = tile_size + grout
    parts = []

    x = -w / 2 + tile_size / 2
    while x < w / 2:
        y = -l / 2 + tile_size / 2
        while y < l / 2:
            tw = min(tile_size, w / 2 - x + tile_size / 2)
            tl = min(tile_size, l / 2 - y + tile_size / 2)
            if tw < 0.05 or tl < 0.05:
                y += step
                continue

            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, -d / 2))
            tile = bpy.context.active_object
            tile.scale = (tw, tl, d)
            bpy.ops.object.transform_apply(scale=True)

            # Wear: sink / raise individual tiles
            if style.wear > 0.3:
                tile.location.z += random.uniform(-0.008, 0.004) * style.wear

            parts.append(tile)
            y += step
        x += step

    return _join(parts, "Floor_Tile")


def _build_asphalt(cfg, style):
    """Asphalt / road surface — rough subdivided slab."""
    w, l, d = cfg["width"], cfg["length"], cfg["depth"]

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -d / 2))
    slab = bpy.context.active_object
    slab.scale = (w, l, d)
    bpy.ops.object.transform_apply(scale=True)
    slab.name = "Floor_Asphalt"

    bm = bmesh.new()
    bm.from_mesh(slab.data)

    cuts = max(3, int(max(w, l) / 0.5))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts,
                              use_grid_fill=True)

    # Rough surface + potholes
    for v in bm.verts:
        if v.co.z > -0.01:  # top surface only
            v.co.z += random.uniform(-0.02, 0.003) * style.wear

    bm.to_mesh(slab.data)
    bm.free()

    # Road markings: add a thin yellow strip (separate material)
    if w >= 2.0:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.001))
        stripe = bpy.context.active_object
        stripe.scale = (0.08, l * 0.8, 0.002)
        bpy.ops.object.transform_apply(scale=True)

        mat = bpy.data.materials.new(name="Road_Stripe")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.85, 0.75, 0.15, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.6
        stripe.data.materials.append(mat)

        # Join stripe to slab
        bpy.ops.object.select_all(action='DESELECT')
        slab.select_set(True)
        stripe.select_set(True)
        bpy.context.view_layer.objects.active = slab
        bpy.ops.object.join()

    return slab


def _build_cobblestone(cfg, style):
    """Cobblestone / brick paving — rounded rectangular stones."""
    w, l, d = cfg["width"], cfg["length"], cfg["depth"]

    stone_w = 0.12
    stone_l = 0.20
    gap = 0.015
    parts = []

    x = -w / 2 + stone_w / 2
    row = 0
    while x < w / 2:
        y_offset = (stone_l / 2 + gap / 2) if row % 2 else 0
        y = -l / 2 + y_offset + stone_l / 2
        while y < l / 2:
            sw = min(stone_w, w / 2 - x + stone_w / 2)
            sl = min(stone_l, l / 2 - y + stone_l / 2)
            if sw < 0.03 or sl < 0.03:
                y += stone_l + gap
                continue

            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, -d / 2))
            stone = bpy.context.active_object
            stone.scale = (
                sw + random.uniform(-0.01, 0.01) * style.wear,
                sl + random.uniform(-0.01, 0.01) * style.wear,
                d + random.uniform(-0.01, 0.005) * style.wear,
            )
            bpy.ops.object.transform_apply(scale=True)

            # Wear: tilt stones
            if style.wear > 0.2:
                stone.rotation_euler.x = random.uniform(-0.04, 0.04) * style.wear
                stone.rotation_euler.y = random.uniform(-0.04, 0.04) * style.wear
                stone.location.z += random.uniform(-0.01, 0.005) * style.wear

            parts.append(stone)
            y += stone_l + gap
        x += stone_w + gap
        row += 1

    return _join(parts, "Floor_Cobblestone")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

BUILDERS = {
    "concrete": _build_concrete,
    "metal_plate": _build_metal_plate,
    "wood_plank": _build_wood_plank,
    "tile": _build_tile,
    "asphalt": _build_asphalt,
    "cobblestone": _build_cobblestone,
}


def create_floor(cfg, variation, style):
    """Create a floor mesh of the given variation.

    Args:
        cfg: dict with 'width', 'length', 'depth'.
        variation: one of BUILDERS keys.
        style: AssetStyle instance.

    Returns:
        The floor Blender object.
    """
    _clear_scene()
    builder = BUILDERS[variation]
    floor = builder(cfg, style)
    floor = _finalize(floor, style, variation)
    return floor
