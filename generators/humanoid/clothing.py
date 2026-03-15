"""Low-poly clothing generation for humanoid characters.

Creates simple clothing meshes that wrap around the body geometry.
Each clothing type is built from basic primitives sized to the character's
body proportions. Clothing objects are returned as (object, bone_name) tuples
so they can be parented to the correct bones for animation.

Available clothing types:
    - "tshirt":    Simple t-shirt covering torso and upper arms
    - "jacket":    Jacket covering torso and full arms
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


# ─── Blender geometry helpers ──────────────────────────────────────────────

def _create_box(bpy, name, size, location):
    """Create a box mesh."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    bpy.ops.object.transform_apply(scale=True)
    return obj


def _create_cylinder(bpy, name, radius, depth, location, segments=8):
    """Create a low-poly cylinder."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segments, radius=radius, depth=depth, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_sphere(bpy, name, radius, location, segments=8, rings=6):
    """Create a low-poly sphere."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings, radius=radius, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _apply_clothing_material(bpy, obj, rgba, roughness=0.85):
    """Apply a solid-color material to a clothing object."""
    mat = bpy.data.materials.new(name=f"{obj.name}_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
    obj.data.materials.append(mat)


def _join_parts(bpy, parts, name="Clothing"):
    """Join multiple objects into one."""
    if not parts:
        return None
    if len(parts) == 1:
        parts[0].name = name
        return parts[0]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = name
    return result


# ─── Clothing builders ────────────────────────────────────────────────────

def _build_tshirt(cfg, color):
    """T-shirt: torso covering + short sleeve tubes."""
    import bpy

    sw = cfg["shoulder_width"]
    td = cfg.get("torso_depth", 0.20)
    torso_len = cfg["torso_length"]
    leg_len = cfg["leg_length"]
    hip_z = 0.06 + leg_len

    parts = []

    # Main torso piece (slightly larger than body)
    torso_h = torso_len * 0.9
    torso = _create_box(bpy, "Shirt_Torso",
                        (sw * 2 + 0.04, td * 1.2, torso_h),
                        (0, 0, hip_z + torso_h / 2 + 0.02))
    parts.append(torso)

    # Short sleeves
    sleeve_len = cfg["arm_length"] * 0.2
    sleeve_r = 0.065 * cfg.get("limb_thickness", 1.0)
    for side, x_sign in [("L", 1), ("R", -1)]:
        sx = x_sign * (sw + 0.04)
        chest_z = hip_z + torso_len
        arm_z = chest_z - 0.06
        sleeve = _create_cylinder(
            bpy, f"Shirt_Sleeve_{side}",
            sleeve_r + 0.015, sleeve_len,
            (sx, 0, arm_z - sleeve_len / 2), segments=8,
        )
        parts.append(sleeve)

    shirt = _join_parts(bpy, parts, "TShirt")
    _apply_clothing_material(bpy, shirt, color)
    return [(shirt, "Spine")]


def _build_jacket(cfg, color):
    """Jacket: full torso + full arm sleeves."""
    import bpy

    sw = cfg["shoulder_width"]
    td = cfg.get("torso_depth", 0.20)
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    lt = cfg.get("limb_thickness", 1.0)
    hip_z = 0.06 + leg_len

    parts = []

    # Torso
    torso_h = torso_len * 0.95
    torso = _create_box(bpy, "Jacket_Torso",
                        (sw * 2 + 0.05, td * 1.25, torso_h),
                        (0, 0, hip_z + torso_h / 2 + 0.01))
    parts.append(torso)

    # Collar
    chest_z = hip_z + torso_len
    neck_len = cfg["neck_length"]
    collar = _create_cylinder(
        bpy, "Jacket_Collar",
        0.07 * lt, neck_len * 0.5,
        (0, 0, chest_z + neck_len * 0.25), segments=8,
    )
    parts.append(collar)

    # Full sleeves
    for side, x_sign in [("L", 1), ("R", -1)]:
        sx = x_sign * (sw + 0.04)
        arm_z = chest_z - 0.06

        # Upper sleeve
        upper_len = arm_len * 0.48
        upper = _create_cylinder(
            bpy, f"Jacket_Upper_{side}",
            0.06 * lt + 0.015, upper_len,
            (sx, 0, arm_z - upper_len / 2), segments=8,
        )
        parts.append(upper)

        # Lower sleeve
        elbow_z = arm_z - upper_len
        lower_len = arm_len * 0.48
        lower = _create_cylinder(
            bpy, f"Jacket_Lower_{side}",
            0.05 * lt + 0.012, lower_len,
            (sx, 0, elbow_z - lower_len / 2), segments=8,
        )
        parts.append(lower)

    jacket = _join_parts(bpy, parts, "Jacket")
    _apply_clothing_material(bpy, jacket, color)
    return [(jacket, "Spine")]


def _build_pants(cfg, color):
    """Pants: waist to ankles."""
    import bpy

    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    leg_len = cfg["leg_length"]
    lt = cfg.get("limb_thickness", 1.0)
    torso_len = cfg["torso_length"]
    hip_z = 0.06 + leg_len

    parts = []

    # Waistband
    waist = _create_box(bpy, "Pants_Waist",
                        (hw * 2 + 0.06, td * 1.0, torso_len * 0.15),
                        (0, 0, hip_z + 0.01))
    parts.append(waist)

    # Legs
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw

        # Upper leg
        knee_z = 0.06 + leg_len * 0.48
        upper_len = hip_z - knee_z
        upper = _create_cylinder(
            bpy, f"Pants_Upper_{side}",
            0.072 * lt, upper_len,
            (x, 0, (hip_z + knee_z) / 2), segments=8,
        )
        parts.append(upper)

        # Lower leg
        ankle_z = 0.1
        lower_len = knee_z - ankle_z
        lower = _create_cylinder(
            bpy, f"Pants_Lower_{side}",
            0.062 * lt, lower_len,
            (x, 0, (knee_z + ankle_z) / 2), segments=8,
        )
        parts.append(lower)

    pants = _join_parts(bpy, parts, "Pants")
    _apply_clothing_material(bpy, pants, color)
    return [(pants, "Hips")]


def _build_shorts(cfg, color):
    """Shorts: waist to above knee."""
    import bpy

    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    leg_len = cfg["leg_length"]
    lt = cfg.get("limb_thickness", 1.0)
    torso_len = cfg["torso_length"]
    hip_z = 0.06 + leg_len
    knee_z = 0.06 + leg_len * 0.48
    shorts_bottom = knee_z + (hip_z - knee_z) * 0.3

    parts = []

    # Waistband
    waist = _create_box(bpy, "Shorts_Waist",
                        (hw * 2 + 0.06, td * 1.0, torso_len * 0.12),
                        (0, 0, hip_z + 0.01))
    parts.append(waist)

    # Short leg tubes
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw
        tube_len = hip_z - shorts_bottom
        tube = _create_cylinder(
            bpy, f"Shorts_Leg_{side}",
            0.074 * lt, tube_len,
            (x, 0, (hip_z + shorts_bottom) / 2), segments=8,
        )
        parts.append(tube)

    shorts = _join_parts(bpy, parts, "Shorts")
    _apply_clothing_material(bpy, shorts, color)
    return [(shorts, "Hips")]


def _build_armor(cfg, color):
    """Armor: chest plate with shoulder pads."""
    import bpy

    sw = cfg["shoulder_width"]
    td = cfg.get("torso_depth", 0.20)
    torso_len = cfg["torso_length"]
    leg_len = cfg["leg_length"]
    hip_z = 0.06 + leg_len
    chest_z = hip_z + torso_len

    parts = []

    # Chest plate
    plate_h = torso_len * 0.7
    plate = _create_box(bpy, "Armor_Plate",
                        (sw * 2 + 0.06, td * 1.35, plate_h),
                        (0, 0, chest_z - plate_h / 2 + 0.02))
    parts.append(plate)

    # Shoulder pads
    for side, x_sign in [("L", 1), ("R", -1)]:
        pad = _create_sphere(
            bpy, f"Armor_Shoulder_{side}",
            0.10,
            (x_sign * (sw + 0.06), 0, chest_z - 0.04),
            segments=8, rings=5,
        )
        pad.scale = (1.0, 0.8, 0.6)
        bpy.context.view_layer.objects.active = pad
        bpy.ops.object.transform_apply(scale=True)
        parts.append(pad)

    # Belt
    belt = _create_box(bpy, "Armor_Belt",
                       (sw * 2 + 0.07, td * 1.1, 0.06),
                       (0, 0, hip_z + torso_len * 0.1))
    parts.append(belt)

    armor = _join_parts(bpy, parts, "Armor")
    roughness = 0.4  # metallic look
    _apply_clothing_material(bpy, armor, color, roughness=roughness)
    return [(armor, "Spine")]


def _build_robe(cfg, color):
    """Robe: full-length garment from shoulders to ankles."""
    import bpy

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    lt = cfg.get("limb_thickness", 1.0)
    hip_z = 0.06 + leg_len
    chest_z = hip_z + torso_len

    parts = []

    # Upper robe (torso)
    torso_h = torso_len * 0.95
    upper = _create_box(bpy, "Robe_Upper",
                        (sw * 2 + 0.05, td * 1.2, torso_h),
                        (0, 0, hip_z + torso_h / 2 + 0.01))
    parts.append(upper)

    # Lower robe (skirt-like, wider at bottom)
    skirt_h = leg_len * 0.85
    skirt_top_w = hw * 2 + 0.06
    skirt_bot_w = hw * 2 + 0.25
    skirt_w = (skirt_top_w + skirt_bot_w) / 2
    skirt = _create_box(bpy, "Robe_Skirt",
                        (skirt_w, td * 1.3, skirt_h),
                        (0, 0, 0.06 + skirt_h / 2))
    parts.append(skirt)

    # Sleeves (wide, flowing)
    for side, x_sign in [("L", 1), ("R", -1)]:
        sx = x_sign * (sw + 0.04)
        arm_z = chest_z - 0.06
        sleeve_len = arm_len * 0.7
        sleeve = _create_cylinder(
            bpy, f"Robe_Sleeve_{side}",
            0.065 * lt + 0.02, sleeve_len,
            (sx, 0, arm_z - sleeve_len / 2), segments=8,
        )
        parts.append(sleeve)

    robe = _join_parts(bpy, parts, "Robe")
    _apply_clothing_material(bpy, robe, color)
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
    import bpy

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
