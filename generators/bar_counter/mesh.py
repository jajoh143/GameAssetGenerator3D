"""Bar counter mesh construction.

Builds a low-poly bar counter (300-500 faces) with:
  - Counter top slab (dark stained wood)
  - Leather padding strip along the front edge
  - Counter body / base cabinet
  - Footrail (thin metal cylinder at base front)
  - Back bar shelf unit (2 tiers)
  - Variation: "straight" (default) or "l_shape" (adds 90-degree wing)

Origin is at the bottom-center of the bar (feet at Z=0).
The bar runs along the X axis; the customer-facing side is +Y.
"""

import bpy
import bmesh
import math
from mathutils import Vector


# ---------------------------------------------------------------------------
# Scene / material helpers
# ---------------------------------------------------------------------------

def _clear_scene():
    """Remove all objects from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def _apply_material(obj, mat_name, color, roughness, metallic):
    """Create and attach a Principled BSDF material with explicit values."""
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    obj.data.materials.append(mat)
    return mat


def _apply_style_material(obj, style, mat_name):
    """Create and attach a Principled BSDF material driven by AssetStyle."""
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = style.get_color()
        bsdf.inputs["Roughness"].default_value = style.get_roughness()
        bsdf.inputs["Metallic"].default_value = style.get_metallic()
    obj.data.materials.append(mat)
    return mat


def _join(parts, name):
    """Join a list of Blender objects into a single named mesh."""
    if not parts:
        bpy.ops.mesh.primitive_cube_add(size=0.01)
        return bpy.context.active_object

    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = name
    return result


def _finalize(obj, name, smooth=True, edge_split_angle=30):
    """Rename, shade-smooth, add EdgeSplit modifier, reset origin."""
    obj.name = name
    bpy.context.view_layer.objects.active = obj
    if smooth:
        bpy.ops.object.shade_smooth()
        mod = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
        mod.split_angle = math.radians(edge_split_angle)
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return obj


# ---------------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------------

def _build_counter_top(w, d, h, thickness, style):
    """Flat rectangular counter top slab — slightly overhangs the front (+Y)."""
    overhang = 0.05   # 5 cm overhang on customer-facing side
    slab_d = d + overhang

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, overhang / 2, h - thickness / 2))
    slab = bpy.context.active_object
    slab.scale = (w, slab_d, thickness)
    bpy.ops.object.transform_apply(scale=True)
    slab.name = "BarCounter_Top"
    _apply_style_material(slab, style, "Mat_CounterWood")
    return slab


def _build_leather_pad(w, h, thickness):
    """Thin leather padding strip along the front edge of the counter top.

    Positioned slightly above the counter surface (~2 cm), ~10 cm wide,
    running the full width along the front lip.
    """
    pad_width = 0.10       # 10 cm deep (Y direction)
    pad_height = 0.02      # 2 cm raised above counter surface
    pad_thickness = 0.015  # thickness of the pad itself

    overhang = 0.05
    # Front face of the counter top is at Y = depth/2 + overhang but we
    # centre the pad just inside/at the front edge.
    front_y = overhang + pad_width / 2 - pad_width

    # Z: sit on top of the counter surface
    pad_z = h + pad_thickness / 2

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, front_y, pad_z))
    pad = bpy.context.active_object
    pad.scale = (w * 0.98, pad_width, pad_thickness)
    bpy.ops.object.transform_apply(scale=True)
    pad.name = "BarCounter_LeatherPad"

    # Leather: very dark brown/black, matte, non-metallic
    LEATHER_COLOR = (0.05, 0.02, 0.02, 1.0)
    _apply_material(pad, "Mat_Leather", LEATHER_COLOR, roughness=0.9, metallic=0.0)
    return pad


def _build_counter_body(w, d, h, style):
    """Boxy base cabinet running from floor to just below counter top."""
    body_h = h - 0.05   # stop just below the top slab
    body_d = d           # same depth as bar, no overhang

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, body_h / 2))
    body = bpy.context.active_object
    body.scale = (w, body_d, body_h)
    bpy.ops.object.transform_apply(scale=True)
    body.name = "BarCounter_Body"
    _apply_style_material(body, style, "Mat_CounterBodyWood")
    return body


def _build_footrail(w, d):
    """Horizontal metal cylinder footrail along the base of the counter front.

    Positioned ~15 cm off the floor, 5 cm in front of the counter face.
    """
    rail_h = 0.15          # 15 cm above floor
    rail_r = 0.02          # 2 cm radius
    front_y = d / 2 + 0.05  # slightly proud of the counter front face

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=rail_r,
        depth=w,
        location=(0, front_y, rail_h),
        rotation=(0, math.radians(90), 0),
    )
    rail = bpy.context.active_object
    rail.name = "BarCounter_Footrail"

    # Chrome metal
    CHROME_COLOR = (0.7, 0.7, 0.75, 1.0)
    _apply_material(rail, "Mat_Chrome", CHROME_COLOR, roughness=0.2, metallic=1.0)
    return rail


def _build_back_shelf(w, h, d, style):
    """2-tier back bar shelf unit behind the counter.

    Positioned at Y = -(depth/2 + 0.1) — the bartender side.
    The unit stands at bar top height and has two shelves for bottles.
    """
    shelf_offset_y = -(d / 2 + 0.1)   # behind the bar body
    shelf_d = 0.35                      # shelf depth (into the wall)
    shelf_t = 0.03                      # shelf plank thickness
    back_panel_t = 0.04                 # back panel thickness

    parts = []

    # --- Back panel (full height) ---
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, shelf_offset_y - shelf_d / 2, h / 2),
    )
    back = bpy.context.active_object
    back.scale = (w, back_panel_t, h)
    bpy.ops.object.transform_apply(scale=True)
    back.name = "Shelf_BackPanel"
    _apply_style_material(back, style, "Mat_ShelfWood")
    parts.append(back)

    # --- Two shelves ---
    shelf_heights = [h * 0.45, h * 0.75]
    for i, sz in enumerate(shelf_heights):
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(0, shelf_offset_y - shelf_d / 2, sz),
        )
        shelf = bpy.context.active_object
        shelf.scale = (w, shelf_d, shelf_t)
        bpy.ops.object.transform_apply(scale=True)
        shelf.name = f"Shelf_Tier{i + 1}"
        _apply_style_material(shelf, style, f"Mat_ShelfWood_T{i + 1}")
        parts.append(shelf)

    # --- Side panels (left and right) ---
    for side_x in (-w / 2 + back_panel_t / 2, w / 2 - back_panel_t / 2):
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(side_x, shelf_offset_y - shelf_d / 2, h / 2),
        )
        side = bpy.context.active_object
        side.scale = (back_panel_t, shelf_d, h)
        bpy.ops.object.transform_apply(scale=True)
        side.name = "Shelf_SidePanel"
        _apply_style_material(side, style, "Mat_ShelfSide")
        parts.append(side)

    return parts


def _build_l_wing(d, h, thickness, style):
    """90-degree wing extending along the +Z (actually +X of a rotated section).

    The wing is a shorter bar section (1.5 m long) extending perpendicular
    to the main bar at one end — classic L-shaped bar layout.

    Wing runs along the Y axis from x = main_width/2 forward.
    """
    wing_w = 1.5           # wing length along Y
    wing_overhang = 0.05
    wing_slab_d = d + wing_overhang
    parts = []

    # Wing counter top — note axes swapped: width -> Y, depth -> X
    # Located at x = 0 (will be offset at join time), runs along Y
    # We build it centred and offset will be done via location
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, wing_w / 2, h - thickness / 2),
    )
    wing_top = bpy.context.active_object
    wing_top.scale = (wing_slab_d, wing_w, thickness)
    bpy.ops.object.transform_apply(scale=True)
    wing_top.name = "Wing_Top"
    _apply_style_material(wing_top, style, "Mat_WingWood")
    parts.append(wing_top)

    # Wing body
    body_h = h - 0.05
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, wing_w / 2, body_h / 2),
    )
    wing_body = bpy.context.active_object
    wing_body.scale = (d, wing_w, body_h)
    bpy.ops.object.transform_apply(scale=True)
    wing_body.name = "Wing_Body"
    _apply_style_material(wing_body, style, "Mat_WingBodyWood")
    parts.append(wing_body)

    # Wing footrail
    rail_r = 0.02
    front_x = d / 2 + 0.05
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=rail_r,
        depth=wing_w,
        location=(front_x, wing_w / 2, 0.15),
        rotation=(math.radians(90), 0, 0),
    )
    wing_rail = bpy.context.active_object
    wing_rail.name = "Wing_Footrail"
    CHROME_COLOR = (0.7, 0.7, 0.75, 1.0)
    _apply_material(wing_rail, "Mat_WingChrome", CHROME_COLOR, roughness=0.2, metallic=1.0)
    parts.append(wing_rail)

    return parts


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def create_bar_counter(cfg, style):
    """Build a bar counter asset from config and style.

    Args:
        cfg: dict with keys: width, depth, height, thickness, shelf_height,
             variation ('straight' | 'l_shape').
        style: AssetStyle instance controlling wood color/roughness.

    Returns:
        The joined, finalized Blender object named "BarCounter".
    """
    _clear_scene()

    w = cfg["width"]
    d = cfg["depth"]
    h = cfg["height"]
    thickness = cfg["thickness"]
    variation = cfg.get("variation", "straight")

    parts = []

    # Core components (shared by all variations)
    parts.append(_build_counter_top(w, d, h, thickness, style))
    parts.append(_build_leather_pad(w, h, thickness))
    parts.append(_build_counter_body(w, d, h, style))
    parts.append(_build_footrail(w, d))
    parts.extend(_build_back_shelf(w, h, d, style))

    # L-shape wing: added at the +X end, perpendicular to main bar
    if variation == "l_shape":
        wing_parts = _build_l_wing(d, h, thickness, style)
        # Offset wing to start at the right end of the main bar
        for p in wing_parts:
            p.location.x += w / 2
        parts.extend(wing_parts)

    obj = _join(parts, "BarCounter")
    obj = _finalize(obj, "BarCounter")
    return obj
