"""Low-poly clothing generation for humanoid characters.

Clothing is generated using the same Skin modifier skeleton as the body mesh,
but with inflated per-vertex radii so the clothing shell perfectly follows
the body's contours. Different clothing types use different subsets of the
skeleton vertices (e.g., t-shirt = spine + upper arms, pants = hips + legs).

Per-joint radius multipliers let each clothing type express its style —
a puffy jacket has larger shoulder radii while tight pants have smaller ones.

Available clothing types:
    - "tshirt":    Simple t-shirt covering torso and upper arms
    - "jacket":    Jacket covering torso and full arms with collar
    - "pants":     Trousers from waist to ankles
    - "shorts":    Short pants from waist to above knee
    - "armor":     Chest plate with shoulder pads (fantasy/medieval)
    - "robe":      Full-length robe from shoulders to ankles

Data constants (CLOTHING_TYPES, CLOTHING_COLORS) are importable without bpy.
Builder functions require Blender's Python environment.
"""

# ─── Data constants (no bpy dependency) ────────────────────────────────────

CLOTHING_TYPES = ("none", "tshirt", "jacket", "pants", "shorts", "armor", "robe")

CLOTHING_COLORS = {
    "white":      (0.85, 0.85, 0.85, 1.0),
    "black":      (0.08, 0.08, 0.08, 1.0),
    "grey":       (0.40, 0.40, 0.40, 1.0),
    "red":        (0.65, 0.10, 0.10, 1.0),
    "blue":       (0.12, 0.20, 0.60, 1.0),
    "green":      (0.15, 0.45, 0.15, 1.0),
    "brown":      (0.35, 0.22, 0.10, 1.0),
    "tan":        (0.65, 0.55, 0.35, 1.0),
    "navy":       (0.08, 0.10, 0.30, 1.0),
    "purple":     (0.35, 0.12, 0.45, 1.0),
    "orange":     (0.75, 0.40, 0.08, 1.0),
    "yellow":     (0.80, 0.75, 0.15, 1.0),
    # Metal / armor
    "steel":      (0.55, 0.56, 0.58, 1.0),
    "gold":       (0.72, 0.60, 0.20, 1.0),
    "bronze":     (0.55, 0.40, 0.18, 1.0),
}


def get_clothing_type_names():
    """Return list of available clothing type names."""
    return list(CLOTHING_TYPES)


def get_clothing_color_names():
    """Return sorted list of available clothing color names."""
    return sorted(CLOTHING_COLORS.keys())


# Default color per clothing type (used when no color is specified)
CLOTHING_DEFAULT_COLORS = {
    "tshirt":  "grey",
    "jacket":  "brown",
    "pants":   "navy",
    "shorts":  "tan",
    "armor":   "steel",
    "robe":    "brown",
}


# ─── Skin-modifier clothing builder ──────────────────────────────────────

def _apply_clothing_material(obj, rgba, roughness=0.85):
    """Apply a solid-color material to a clothing object."""
    import bpy
    mat = bpy.data.materials.new(name=f"{obj.name}_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
    obj.data.materials.append(mat)


def _build_skin_clothing(cfg, name, vertex_mask, radii_multipliers,
                         branch_smoothing=0.7, extra_parts_fn=None):
    """Build a clothing piece using the body's Skin modifier skeleton.

    Takes the same skeleton as the body but keeps only the vertices in
    vertex_mask, and inflates their radii by the multipliers. This produces
    a clothing mesh that perfectly follows the body's contours.

    Args:
        cfg: body config dict
        name: object name for the clothing piece
        vertex_mask: set of vertex indices to include
        radii_multipliers: dict mapping vertex index to (rx_mult, ry_mult),
            or a single (rx_mult, ry_mult) tuple for uniform inflation
        branch_smoothing: smoothness at branch junctions
        extra_parts_fn: optional callable(bpy, cfg, clothing_obj) that adds
            extra geometry (e.g., collar, skirt cone) and returns a list of
            extra objects to join with the clothing

    Returns:
        The clothing mesh object (modifiers applied, material not yet set).
    """
    import bpy
    from .mesh import build_body_skeleton, _apply_skin_modifier

    verts, edges, radii = build_body_skeleton(cfg)

    # Default multiplier
    if isinstance(radii_multipliers, tuple):
        default_mult = radii_multipliers
    else:
        default_mult = (1.12, 1.12)

    # Filter to only vertices in mask, remap indices
    old_to_new = {}
    new_verts = []
    new_radii = {}
    for old_idx in sorted(vertex_mask):
        new_idx = len(new_verts)
        old_to_new[old_idx] = new_idx
        new_verts.append(verts[old_idx])
        rx, ry = radii[old_idx]
        if isinstance(radii_multipliers, dict):
            mx, my = radii_multipliers.get(old_idx, default_mult)
        else:
            mx, my = radii_multipliers
        new_radii[new_idx] = (rx * mx, ry * my)

    # Filter edges to only those where both endpoints are in mask
    new_edges = []
    for a, b in edges:
        if a in old_to_new and b in old_to_new:
            new_edges.append((old_to_new[a], old_to_new[b]))

    # Build the skin mesh
    clothing_obj = _apply_skin_modifier(
        new_verts, new_edges, new_radii,
        name=name, branch_smoothing=branch_smoothing, subsurf_level=1,
    )

    # Add extra geometry if needed (collar, skirt, etc.)
    if extra_parts_fn:
        extra_objs = extra_parts_fn(bpy, cfg, clothing_obj)
        if extra_objs:
            all_objs = [clothing_obj] + extra_objs
            bpy.ops.object.select_all(action='DESELECT')
            for obj in all_objs:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = clothing_obj
            bpy.ops.object.join()
            clothing_obj = bpy.context.active_object

    # Smooth shading
    bpy.context.view_layer.objects.active = clothing_obj
    bpy.ops.object.shade_smooth()
    clothing_obj.name = name

    return clothing_obj


# ─── Clothing builders ────────────────────────────────────────────────────

def _build_tshirt(cfg, color):
    """T-shirt: torso + upper arms (to deltoid/bicep area)."""
    from .mesh import (V_LOWER_WAIST, V_WAIST,
                       V_LOWER_CHEST, V_CHEST,
                       V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID, V_L_BICEP,
                       V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID, V_R_BICEP)

    # Torso spine (lower waist to chest) + short sleeves (to bicep)
    # Shirt hem sits at V_LOWER_WAIST (belly button) — above the pants waistband
    vertex_mask = {
        V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST, V_CHEST,
        V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID, V_L_BICEP,
        V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID, V_R_BICEP,
    }

    # Slightly loose fit — 1.12x body radii, sleeves tighter
    mults = {}
    for v in vertex_mask:
        mults[v] = (1.12, 1.12)
    # Sleeves slightly tighter at the ends
    for v in (V_L_BICEP, V_R_BICEP):
        mults[v] = (1.08, 1.08)

    shirt = _build_skin_clothing(cfg, "TShirt", vertex_mask, mults)
    _apply_clothing_material(shirt, color)
    return [(shirt, "Spine")]


def _build_jacket(cfg, color):
    """Jacket: torso + full arms + collar."""
    from .mesh import (V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST, V_CHEST,
                       V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID,
                       V_L_BICEP, V_L_ELBOW, V_L_FOREARM, V_L_WRIST,
                       V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID,
                       V_R_BICEP, V_R_ELBOW, V_R_FOREARM, V_R_WRIST)
    import bpy

    vertex_mask = {
        V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST, V_CHEST,
        V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID,
        V_L_BICEP, V_L_ELBOW, V_L_FOREARM, V_L_WRIST,
        V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID,
        V_R_BICEP, V_R_ELBOW, V_R_FOREARM, V_R_WRIST,
    }

    # Puffy at shoulders, tighter at wrists
    mults = {}
    for v in vertex_mask:
        mults[v] = (1.18, 1.18)
    for v in (V_L_FOREARM, V_R_FOREARM):
        mults[v] = (1.12, 1.12)
    for v in (V_L_WRIST, V_R_WRIST):
        mults[v] = (1.10, 1.10)

    def _add_collar(bpy_mod, _cfg, _clothing):
        """Add a collar cylinder above the chest."""
        neck_len = _cfg["neck_length"]
        lt = _cfg.get("limb_thickness", 1.0)
        chest_z = 0.06 + _cfg["leg_length"] + _cfg["torso_length"]
        bpy_mod.ops.mesh.primitive_cylinder_add(
            vertices=10, radius=0.07 * lt,
            depth=neck_len * 0.4,
            location=(0, 0, chest_z + neck_len * 0.2),
        )
        collar = bpy_mod.context.active_object
        collar.name = "Jacket_Collar"
        return [collar]

    jacket = _build_skin_clothing(cfg, "Jacket", vertex_mask, mults,
                                  extra_parts_fn=_add_collar)
    _apply_clothing_material(jacket, color)
    return [(jacket, "Spine")]


def _build_pants(cfg, color):
    """Pants: waist/hip area + full legs to ankles."""
    from .mesh import (V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST,
                       V_L_HIP_JOINT, V_L_THIGH, V_L_KNEE, V_L_CALF, V_L_ANKLE,
                       V_R_HIP_JOINT, V_R_THIGH, V_R_KNEE, V_R_CALF, V_R_ANKLE)

    vertex_mask = {
        V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST,
        V_L_HIP_JOINT, V_L_THIGH, V_L_KNEE, V_L_CALF, V_L_ANKLE,
        V_R_HIP_JOINT, V_R_THIGH, V_R_KNEE, V_R_CALF, V_R_ANKLE,
    }

    # Fitted pants — generous clearance over body to prevent bleed-through
    mults = {}
    for v in vertex_mask:
        mults[v] = (1.28, 1.28)
    for v in (V_L_HIP_JOINT, V_R_HIP_JOINT):
        mults[v] = (1.32, 1.32)
    for v in (V_L_THIGH, V_R_THIGH):
        mults[v] = (1.30, 1.30)
    for v in (V_L_CALF, V_R_CALF):
        mults[v] = (1.26, 1.26)
    for v in (V_L_KNEE, V_R_KNEE):
        mults[v] = (1.24, 1.24)
    for v in (V_L_ANKLE, V_R_ANKLE):
        mults[v] = (1.20, 1.20)

    pants = _build_skin_clothing(cfg, "Pants", vertex_mask, mults)
    _apply_clothing_material(pants, color)
    return [(pants, "Hips")]


def _build_shorts(cfg, color):
    """Shorts: waist/hip + upper legs only (to knee area)."""
    from .mesh import (V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST,
                       V_L_HIP_JOINT, V_L_THIGH, V_L_KNEE,
                       V_R_HIP_JOINT, V_R_THIGH, V_R_KNEE)

    vertex_mask = {
        V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST,
        V_L_HIP_JOINT, V_L_THIGH, V_L_KNEE,
        V_R_HIP_JOINT, V_R_THIGH, V_R_KNEE,
    }

    # Loose fit shorts — generous clearance over body
    mults = {}
    for v in vertex_mask:
        mults[v] = (1.30, 1.30)
    for v in (V_L_HIP_JOINT, V_R_HIP_JOINT):
        mults[v] = (1.34, 1.34)
    for v in (V_L_THIGH, V_R_THIGH):
        mults[v] = (1.32, 1.32)
    # Looser at the hem
    for v in (V_L_KNEE, V_R_KNEE):
        mults[v] = (1.28, 1.28)

    shorts = _build_skin_clothing(cfg, "Shorts", vertex_mask, mults)
    _apply_clothing_material(shorts, color)
    return [(shorts, "Hips")]


def _build_armor(cfg, color):
    """Armor: thick chest plate with shoulder pads."""
    from .mesh import (V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST, V_CHEST,
                       V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID,
                       V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID)

    vertex_mask = {
        V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST, V_CHEST,
        V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID,
        V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID,
    }

    # Thick armor — 1.25x at chest, big shoulder pads
    mults = {}
    for v in vertex_mask:
        mults[v] = (1.22, 1.25)
    # Big shoulder pads
    for v in (V_L_SHOULDER, V_R_SHOULDER, V_L_DELTOID, V_R_DELTOID):
        mults[v] = (1.40, 1.35)

    armor = _build_skin_clothing(cfg, "Armor", vertex_mask, mults,
                                 branch_smoothing=0.5)
    _apply_clothing_material(armor, color, roughness=0.4)
    return [(armor, "Spine")]


def _build_robe(cfg, color):
    """Robe: full torso + long sleeves + skirt cone."""
    from .mesh import (V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST,
                       V_LOWER_CHEST, V_CHEST,
                       V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID,
                       V_L_BICEP, V_L_ELBOW, V_L_FOREARM,
                       V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID,
                       V_R_BICEP, V_R_ELBOW, V_R_FOREARM)
    import bpy

    vertex_mask = {
        V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST, V_CHEST,
        V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID,
        V_L_BICEP, V_L_ELBOW, V_L_FOREARM,
        V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID,
        V_R_BICEP, V_R_ELBOW, V_R_FOREARM,
    }

    # Loose robe — flowing sleeves
    mults = {}
    for v in vertex_mask:
        mults[v] = (1.15, 1.15)
    # Wider flowing sleeves at the ends
    for v in (V_L_FOREARM, V_R_FOREARM):
        mults[v] = (1.30, 1.30)

    def _add_skirt(bpy_mod, _cfg, _clothing):
        """Add a cone skirt from waist to ankles."""
        hw = _cfg["hip_width"]
        leg_len = _cfg["leg_length"]
        hip_z = 0.06 + leg_len
        waist_half_w = min(_cfg["shoulder_width"], hw) * 0.85
        skirt_h = leg_len * 0.85
        skirt_bottom_r = hw + 0.18
        bpy_mod.ops.mesh.primitive_cone_add(
            vertices=12,
            radius1=skirt_bottom_r,
            radius2=waist_half_w + 0.015,
            depth=skirt_h,
            location=(0, 0, hip_z - skirt_h / 2),
        )
        skirt = bpy_mod.context.active_object
        skirt.name = "Robe_Skirt"
        return [skirt]

    robe = _build_skin_clothing(cfg, "Robe", vertex_mask, mults,
                                extra_parts_fn=_add_skirt)
    _apply_clothing_material(robe, color)
    return [(robe, "Spine")]


# ─── Dispatch ──────────────────────────────────────────────────────────────

CLOTHING_BUILDERS = {
    "tshirt":  _build_tshirt,
    "jacket":  _build_jacket,
    "pants":   _build_pants,
    "shorts":  _build_shorts,
    "armor":   _build_armor,
    "robe":    _build_robe,
}


def create_clothing(cfg, clothing_spec, color=None):
    """Create clothing geometry for a humanoid character.

    Args:
        cfg: dict with body proportion values.
        clothing_spec: Clothing type name, or comma-separated list
            (e.g. "tshirt,pants"), or a list of names.
        color: RGBA tuple, named color string, or None for per-type defaults.
            When None, each piece uses its own default color (e.g. grey for
            shirts, navy for pants). When specified, all pieces share the color.

    Returns:
        List of (blender_object, bone_name) tuples.
    """
    if clothing_spec == "none" or not clothing_spec:
        return []

    # Resolve override color (None means use per-type defaults)
    override_rgba = None
    if color is not None:
        if isinstance(color, str):
            override_rgba = CLOTHING_COLORS.get(color, CLOTHING_COLORS["grey"])
        else:
            override_rgba = tuple(color)

    # Parse clothing spec into list
    if isinstance(clothing_spec, str):
        types = [t.strip() for t in clothing_spec.split(",")]
    else:
        types = list(clothing_spec)

    results = []
    for ctype in types:
        if ctype in CLOTHING_BUILDERS:
            if override_rgba is not None:
                rgba = override_rgba
            else:
                default_name = CLOTHING_DEFAULT_COLORS.get(ctype, "grey")
                rgba = CLOTHING_COLORS[default_name]
            pieces = CLOTHING_BUILDERS[ctype](cfg, rgba)
            results.extend(pieces)

    return results
