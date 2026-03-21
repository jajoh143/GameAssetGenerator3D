"""Bottle mesh construction.

Builds three components using bmesh ring-sweep geometry:
  1. Bottle body  — lathe-profile from bottom rings to mouth
  2. Label band   — thin cylinder slice around the body mid-section
  3. Cap          — small cylinder at the mouth (crown cap / cork)

Each component gets its own material before everything is joined into a
single "Bottle" object.  Feet sit at Z=0.
"""

import bpy
import bmesh
import math


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clear_scene():
    """Remove all existing scene objects."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def _apply_single_material(obj, mat_name, color, roughness, metallic, alpha=1.0):
    """Attach a Principled BSDF material to *obj* (single slot)."""
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = "BLEND"
    obj.data.materials.append(mat)
    return mat


def _join(parts, name):
    """Join a list of Blender objects into one mesh named *name*."""
    if not parts:
        bpy.ops.mesh.primitive_cube_add(size=0.01)
        result = bpy.context.active_object
        result.name = name
        return result

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
    """Rename, shade-smooth, add EdgeSplit, reset origin to world origin."""
    obj.name = name
    bpy.context.view_layer.objects.active = obj
    if smooth:
        bpy.ops.object.shade_smooth()
        mod = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
        mod.split_angle = math.radians(edge_split_angle)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return obj


# ---------------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------------

def _build_bottle_body(cfg):
    """Build the main bottle body using a bmesh ring-sweep (lathe) profile.

    Rings are defined as (z_height, radius) pairs from bottom to top.
    Adjacent rings are connected with quad faces; the bottom and top are
    capped with triangle fans.

    Returns:
        The body Blender mesh object (not yet linked with a material).
    """
    h = cfg["height"]
    seg = cfg["segments"]
    body_r = cfg["body_radius"]
    neck_r = cfg["neck_radius"]
    body_h = h * cfg["body_height_ratio"]
    shoulder_h = h * cfg["shoulder_height_ratio"]
    neck_h = h * cfg["neck_height_ratio"]
    # mouth_h fills whatever remains at the top
    # (body_h + shoulder_h + neck_h + mouth_h == h)

    rings = [
        (0.0,                                    body_r * 0.85),  # base chamfer
        (0.02,                                   body_r),          # base edge
        (body_h * 0.5,                           body_r),          # mid body
        (body_h,                                 body_r),          # shoulder start
        (body_h + shoulder_h,                    neck_r * 1.5),   # shoulder end / neck base
        (body_h + shoulder_h + neck_h * 0.5,    neck_r),          # mid neck
        (body_h + shoulder_h + neck_h,           neck_r * 1.1),   # mouth flare
    ]

    bm = bmesh.new()
    prev_verts = None

    for z, r in rings:
        verts = []
        for i in range(seg):
            angle = 2.0 * math.pi * i / seg
            v = bm.verts.new((r * math.cos(angle), r * math.sin(angle), z))
            verts.append(v)
        if prev_verts is not None:
            for i in range(seg):
                bm.faces.new([
                    prev_verts[i],
                    prev_verts[(i + 1) % seg],
                    verts[(i + 1) % seg],
                    verts[i],
                ])
        prev_verts = verts

    # Cap bottom with a triangle fan
    bottom_center = bm.verts.new((0.0, 0.0, 0.0))
    bm.verts.ensure_lookup_table()
    base_ring = [v for v in bm.verts if abs(v.co.z) < 0.0005 and v is not bottom_center]
    for i in range(len(base_ring)):
        bm.faces.new([bottom_center, base_ring[i], base_ring[(i + 1) % len(base_ring)]])

    # Cap top with a triangle fan
    top_z = rings[-1][0]
    top_center = bm.verts.new((0.0, 0.0, top_z))
    bm.verts.ensure_lookup_table()
    top_ring = [v for v in bm.verts if abs(v.co.z - top_z) < 0.0005 and v is not top_center]
    for i in range(len(top_ring)):
        # Winding order flipped so the face normal points upward (+Z)
        bm.faces.new([top_center, top_ring[(i + 1) % len(top_ring)], top_ring[i]])

    mesh = bpy.data.meshes.new("BottleBody")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("BottleBody", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _build_label(cfg, bottle_obj):
    """Build a thin cylinder-slice label band around the bottle body.

    The label sits at the vertical centre of the body section, scaled to
    just outside the body radius.  It uses a simple cylinder whose height
    equals label_height_ratio * body_height.

    Returns:
        Label Blender object, or None if has_label is False.
    """
    if not cfg.get("has_label", True):
        return None

    h = cfg["height"]
    seg = cfg["segments"]
    body_r = cfg["body_radius"]
    body_h = h * cfg["body_height_ratio"]
    label_h = body_h * cfg["label_height_ratio"]
    label_r = body_r + 0.001   # sit just outside the glass surface

    # Centre the label vertically in the body section
    label_z_center = body_h * 0.5
    label_z_bottom = label_z_center - label_h / 2.0

    bm = bmesh.new()

    # Bottom ring of label
    bot_verts = []
    for i in range(seg):
        angle = 2.0 * math.pi * i / seg
        v = bm.verts.new((label_r * math.cos(angle), label_r * math.sin(angle), label_z_bottom))
        bot_verts.append(v)

    # Top ring of label
    top_verts = []
    for i in range(seg):
        angle = 2.0 * math.pi * i / seg
        v = bm.verts.new((label_r * math.cos(angle), label_r * math.sin(angle), label_z_bottom + label_h))
        top_verts.append(v)

    # Side quads
    for i in range(seg):
        bm.faces.new([
            bot_verts[i],
            bot_verts[(i + 1) % seg],
            top_verts[(i + 1) % seg],
            top_verts[i],
        ])

    # Cap bottom
    bc = bm.verts.new((0.0, 0.0, label_z_bottom))
    for i in range(seg):
        bm.faces.new([bc, bot_verts[i], bot_verts[(i + 1) % seg]])

    # Cap top
    tc = bm.verts.new((0.0, 0.0, label_z_bottom + label_h))
    for i in range(seg):
        bm.faces.new([tc, top_verts[(i + 1) % seg], top_verts[i]])

    mesh = bpy.data.meshes.new("BottleLabel")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("BottleLabel", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _build_cap(cfg):
    """Build a small cylinder cap at the very top of the neck.

    The cap is placed at the mouth of the bottle (top of the last ring in
    the body profile) and extends a few millimetres upward.

    Returns:
        Cap Blender object.
    """
    h = cfg["height"]
    seg = cfg["segments"]
    neck_r = cfg["neck_radius"]
    body_h = h * cfg["body_height_ratio"]
    shoulder_h = h * cfg["shoulder_height_ratio"]
    neck_h = h * cfg["neck_height_ratio"]

    # Mouth sits at the top of the neck section
    mouth_z = body_h + shoulder_h + neck_h
    cap_height = 0.008          # 8 mm crown cap
    cap_r = neck_r * 1.25      # slightly wider than the neck

    bm = bmesh.new()

    bot_verts = []
    for i in range(seg):
        angle = 2.0 * math.pi * i / seg
        v = bm.verts.new((cap_r * math.cos(angle), cap_r * math.sin(angle), mouth_z))
        bot_verts.append(v)

    top_verts = []
    for i in range(seg):
        angle = 2.0 * math.pi * i / seg
        v = bm.verts.new((cap_r * math.cos(angle), cap_r * math.sin(angle), mouth_z + cap_height))
        top_verts.append(v)

    # Side quads
    for i in range(seg):
        bm.faces.new([
            bot_verts[i],
            bot_verts[(i + 1) % seg],
            top_verts[(i + 1) % seg],
            top_verts[i],
        ])

    # Bottom cap
    bc = bm.verts.new((0.0, 0.0, mouth_z))
    for i in range(seg):
        bm.faces.new([bc, bot_verts[i], bot_verts[(i + 1) % seg]])

    # Top cap
    tc = bm.verts.new((0.0, 0.0, mouth_z + cap_height))
    for i in range(seg):
        bm.faces.new([tc, top_verts[(i + 1) % seg], top_verts[i]])

    mesh = bpy.data.meshes.new("BottleCap")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("BottleCap", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _apply_bottle_materials(bottle_obj, label_obj, cap_obj, cfg):
    """Apply per-component materials before joining.

    Each component has its own material slot:
      - glass  : Principled BSDF with alpha for translucency
      - label  : Opaque paper/print material
      - cap    : Metal / painted-metal
    """
    # Glass material (translucent)
    _apply_single_material(
        bottle_obj,
        mat_name="BottleGlass",
        color=cfg["glass_color"],
        roughness=cfg["glass_roughness"],
        metallic=cfg["glass_metallic"],
        alpha=cfg["glass_alpha"],
    )

    # Label material (opaque)
    if label_obj is not None:
        _apply_single_material(
            label_obj,
            mat_name="BottleLabel",
            color=cfg["label_color"],
            roughness=0.7,
            metallic=0.0,
            alpha=1.0,
        )

    # Cap material (metallic crown cap)
    _apply_single_material(
        cap_obj,
        mat_name="BottleCap",
        color=cfg["cap_color"],
        roughness=0.3,
        metallic=0.6,
        alpha=1.0,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_bottle(cfg, style):
    """Create the full bottle asset and return the joined Blender object.

    Args:
        cfg:   Config dict (merged from DEFAULT_CFG + user overrides).
        style: AssetStyle instance (used for fallback; bottle cfg overrides
               colour/roughness directly so style is largely unused here).

    Returns:
        The finalised "Bottle" Blender object.
    """
    _clear_scene()

    # Build components
    bottle_obj = _build_bottle_body(cfg)
    label_obj = _build_label(cfg, bottle_obj) if cfg.get("has_label", True) else None
    cap_obj = _build_cap(cfg)

    # Apply materials before joining (so each part keeps its own slot)
    _apply_bottle_materials(bottle_obj, label_obj, cap_obj, cfg)

    # Gather non-None parts
    parts = [bottle_obj]
    if label_obj is not None:
        parts.append(label_obj)
    parts.append(cap_obj)

    # Join into a single object and finalise
    result = _join(parts, "Bottle")
    return _finalize(result, "Bottle")
