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

def _create_cone(bpy, name, r_bottom, r_top, depth, location, segments=12):
    """Create a truncated cone (matches body mesh style)."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments,
        radius1=r_bottom,
        radius2=r_top,
        depth=depth,
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_cylinder(bpy, name, radius, depth, location, segments=10):
    """Create a cylinder."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segments, radius=radius, depth=depth, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_sphere(bpy, name, radius, location, segments=8, rings=6):
    """Create a sphere."""
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


# ─── Shared body layout helpers ────────────────────────────────────────────

def _create_box(bpy, name, size, location):
    """Create a box mesh."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    bpy.ops.object.transform_apply(scale=True)
    return obj


def _body_layout(cfg):
    """Compute key Z positions and widths matching mesh.py body layout."""
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.35
    chest_z = hip_z + torso_len
    waist_half_w = min(sw, hw) * 0.85
    shoulder_x = sw + 0.04  # arm attachment X

    return {
        "foot_top": foot_top, "knee_z": knee_z, "hip_z": hip_z,
        "waist_z": waist_z, "chest_z": chest_z,
        "sw": sw, "hw": hw, "td": td,
        "waist_half_w": waist_half_w, "shoulder_x": shoulder_x,
    }


# ─── Clothing builders ────────────────────────────────────────────────────

def _build_tshirt(cfg, color):
    """T-shirt: box torso + shoulder covers + short sleeves."""
    import bpy

    lay = _body_layout(cfg)
    sw, hw, td = lay["sw"], lay["hw"], lay["td"]
    hip_z, chest_z = lay["hip_z"], lay["chest_z"]
    waist_half_w = lay["waist_half_w"]
    shoulder_x = lay["shoulder_x"]
    torso_len = cfg["torso_length"]
    lt = cfg.get("limb_thickness", 1.0)
    arm_len = cfg["arm_length"]
    off = 0.012

    parts = []

    # Upper torso (chest — full shoulder width)
    upper_h = torso_len * 0.50
    upper = _create_box(bpy, "Shirt_Upper",
                        (sw * 2 + off * 2, td * 1.1 + off * 2, upper_h),
                        (0, 0, chest_z - upper_h / 2))
    parts.append(upper)

    # Lower torso (waist — narrower)
    waist_w = waist_half_w * 2
    lower_h = torso_len * 0.45
    lower = _create_box(bpy, "Shirt_Lower",
                        (waist_w + off * 2, td * 0.95 + off * 2, lower_h),
                        (0, 0, hip_z + lower_h / 2 + 0.02))
    parts.append(lower)

    # Shoulder covers + sleeves — box over shoulder bridging to arm cylinder
    sleeve_len = arm_len * 0.22
    arm_z = chest_z - 0.06
    for side, x_sign in [("L", 1), ("R", -1)]:
        sx = x_sign * shoulder_x

        # Shoulder cover (box bridging chest edge to arm)
        bridge_w = shoulder_x - sw + 0.03
        bridge = _create_box(
            bpy, f"Shirt_Shoulder_{side}",
            (bridge_w + off, td * 0.85 + off, 0.07),
            (x_sign * (sw + bridge_w / 2 - 0.01), 0, chest_z - 0.03),
        )
        parts.append(bridge)

        # Sleeve (cylinder covering upper arm)
        sleeve = _create_cone(
            bpy, f"Shirt_Sleeve_{side}",
            r_bottom=0.048 * lt + off, r_top=0.060 * lt + off,
            depth=sleeve_len,
            location=(sx, 0, arm_z - sleeve_len / 2),
            segments=10,
        )
        parts.append(sleeve)

    shirt = _join_parts(bpy, parts, "TShirt")
    _apply_clothing_material(bpy, shirt, color)
    return [(shirt, "Spine")]


def _build_jacket(cfg, color):
    """Jacket: box torso + shoulder covers + full arm sleeves + collar."""
    import bpy

    lay = _body_layout(cfg)
    sw, hw, td = lay["sw"], lay["hw"], lay["td"]
    hip_z, chest_z = lay["hip_z"], lay["chest_z"]
    waist_half_w = lay["waist_half_w"]
    shoulder_x = lay["shoulder_x"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]
    neck_len = cfg["neck_length"]
    lt = cfg.get("limb_thickness", 1.0)
    off = 0.015

    parts = []

    # Upper torso
    upper_h = torso_len * 0.50
    upper = _create_box(bpy, "Jacket_Upper",
                        (sw * 2 + off * 2, td * 1.1 + off * 2, upper_h),
                        (0, 0, chest_z - upper_h / 2))
    parts.append(upper)

    # Lower torso
    waist_w = waist_half_w * 2
    lower_h = torso_len * 0.48
    lower = _create_box(bpy, "Jacket_Lower",
                        (waist_w + off * 2, td * 0.95 + off * 2, lower_h),
                        (0, 0, hip_z + lower_h / 2))
    parts.append(lower)

    # Collar
    collar = _create_cylinder(bpy, "Jacket_Collar",
                              0.07 * lt, neck_len * 0.5,
                              (0, 0, chest_z + neck_len * 0.25), segments=10)
    parts.append(collar)

    # Shoulder covers + full sleeves
    arm_z = chest_z - 0.06
    for side, x_sign in [("L", 1), ("R", -1)]:
        sx = x_sign * shoulder_x

        # Shoulder cover
        bridge_w = shoulder_x - sw + 0.03
        bridge = _create_box(bpy, f"Jacket_Shoulder_{side}",
                             (bridge_w + off, td * 0.85 + off, 0.08),
                             (x_sign * (sw + bridge_w / 2 - 0.01), 0, chest_z - 0.03))
        parts.append(bridge)

        # Upper sleeve
        upper_len = arm_len * 0.48
        elbow_z = arm_z - upper_len
        upper_sl = _create_cone(bpy, f"Jacket_UpperSl_{side}",
                                r_bottom=0.045 * lt + off, r_top=0.06 * lt + off,
                                depth=upper_len,
                                location=(sx, 0, (arm_z + elbow_z) / 2), segments=10)
        parts.append(upper_sl)

        # Lower sleeve
        lower_len = arm_len * 0.48
        lower_sl = _create_cone(bpy, f"Jacket_LowerSl_{side}",
                                r_bottom=0.037 * lt + off, r_top=0.047 * lt + off,
                                depth=lower_len,
                                location=(sx, 0, elbow_z - lower_len / 2), segments=10)
        parts.append(lower_sl)

    jacket = _join_parts(bpy, parts, "Jacket")
    _apply_clothing_material(bpy, jacket, color)
    return [(jacket, "Spine")]


def _build_pants(cfg, color):
    """Pants: box waistband + tapered leg tubes from hips to ankles."""
    import bpy

    lay = _body_layout(cfg)
    hw, td = lay["hw"], lay["td"]
    hip_z, knee_z = lay["hip_z"], lay["knee_z"]
    waist_half_w = lay["waist_half_w"]
    torso_len = cfg["torso_length"]
    leg_len = cfg["leg_length"]
    lt = cfg.get("limb_thickness", 1.0)
    off = 0.012

    parts = []

    # Waistband (box matching lower torso)
    waist_h = torso_len * 0.15
    waist_w = waist_half_w * 2
    waist = _create_box(bpy, "Pants_Waist",
                        (waist_w + off * 2, td * 0.95 + off * 2, waist_h),
                        (0, 0, hip_z + waist_h / 2))
    parts.append(waist)

    # Legs (tapered)
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw

        upper_len = hip_z - knee_z
        upper = _create_cone(bpy, f"Pants_Upper_{side}",
                             r_bottom=0.060 * lt + off, r_top=0.074 * lt + off,
                             depth=upper_len,
                             location=(x, 0, (hip_z + knee_z) / 2), segments=10)
        parts.append(upper)

        ankle_z = 0.1
        lower_len = knee_z - ankle_z
        lower = _create_cone(bpy, f"Pants_Lower_{side}",
                             r_bottom=0.050 * lt + off, r_top=0.062 * lt + off,
                             depth=lower_len,
                             location=(x, 0, (knee_z + ankle_z) / 2), segments=10)
        parts.append(lower)

    pants = _join_parts(bpy, parts, "Pants")
    _apply_clothing_material(bpy, pants, color)
    return [(pants, "Hips")]


def _build_shorts(cfg, color):
    """Shorts: box waistband + short tapered leg tubes."""
    import bpy

    lay = _body_layout(cfg)
    hw, td = lay["hw"], lay["td"]
    hip_z, knee_z = lay["hip_z"], lay["knee_z"]
    waist_half_w = lay["waist_half_w"]
    torso_len = cfg["torso_length"]
    lt = cfg.get("limb_thickness", 1.0)
    off = 0.012
    shorts_bottom = knee_z + (hip_z - knee_z) * 0.3

    parts = []

    # Waistband
    waist_h = torso_len * 0.12
    waist_w = waist_half_w * 2
    waist = _create_box(bpy, "Shorts_Waist",
                        (waist_w + off * 2, td * 0.95 + off * 2, waist_h),
                        (0, 0, hip_z + waist_h / 2))
    parts.append(waist)

    # Short legs
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw
        tube_len = hip_z - shorts_bottom
        tube = _create_cone(bpy, f"Shorts_Leg_{side}",
                            r_bottom=0.064 * lt + off, r_top=0.076 * lt + off,
                            depth=tube_len,
                            location=(x, 0, (hip_z + shorts_bottom) / 2), segments=10)
        parts.append(tube)

    shorts = _join_parts(bpy, parts, "Shorts")
    _apply_clothing_material(bpy, shorts, color)
    return [(shorts, "Hips")]


def _build_armor(cfg, color):
    """Armor: box chest plate with shoulder pads and belt."""
    import bpy

    lay = _body_layout(cfg)
    sw, hw, td = lay["sw"], lay["hw"], lay["td"]
    hip_z, chest_z = lay["hip_z"], lay["chest_z"]
    waist_half_w = lay["waist_half_w"]
    shoulder_x = lay["shoulder_x"]
    torso_len = cfg["torso_length"]
    off = 0.018

    parts = []

    # Upper plate (chest width)
    upper_h = torso_len * 0.50
    upper = _create_box(bpy, "Armor_Upper",
                        (sw * 2 + off * 2, td * 1.3 + off * 2, upper_h),
                        (0, 0, chest_z - upper_h / 2))
    parts.append(upper)

    # Lower plate (waist)
    waist_w = waist_half_w * 2
    lower_h = torso_len * 0.30
    lower = _create_box(bpy, "Armor_Lower",
                        (waist_w + off * 2, td * 1.15 + off * 2, lower_h),
                        (0, 0, chest_z - upper_h - lower_h / 2 + 0.02))
    parts.append(lower)

    # Shoulder pads
    for side, x_sign in [("L", 1), ("R", -1)]:
        pad = _create_sphere(bpy, f"Armor_Shoulder_{side}", 0.10,
                             (x_sign * shoulder_x, 0, chest_z - 0.02),
                             segments=8, rings=5)
        pad.scale = (1.2, 0.9, 0.7)
        bpy.context.view_layer.objects.active = pad
        bpy.ops.object.transform_apply(scale=True)
        parts.append(pad)

    # Belt
    belt = _create_box(bpy, "Armor_Belt",
                       (waist_w + off * 2 + 0.02, td * 1.0, 0.06),
                       (0, 0, hip_z + torso_len * 0.1))
    parts.append(belt)

    armor = _join_parts(bpy, parts, "Armor")
    _apply_clothing_material(bpy, armor, color, roughness=0.4)
    return [(armor, "Spine")]


def _build_robe(cfg, color):
    """Robe: box torso + shoulder covers + wide skirt + long sleeves."""
    import bpy

    lay = _body_layout(cfg)
    sw, hw, td = lay["sw"], lay["hw"], lay["td"]
    hip_z, chest_z = lay["hip_z"], lay["chest_z"]
    waist_half_w = lay["waist_half_w"]
    shoulder_x = lay["shoulder_x"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    lt = cfg.get("limb_thickness", 1.0)
    off = 0.015

    parts = []

    # Upper torso (box, shoulder width)
    upper_h = torso_len * 0.50
    upper = _create_box(bpy, "Robe_Upper",
                        (sw * 2 + off * 2, td * 1.1 + off * 2, upper_h),
                        (0, 0, chest_z - upper_h / 2))
    parts.append(upper)

    # Lower torso (box, waist width)
    waist_w = waist_half_w * 2
    lower_h = torso_len * 0.50
    lower = _create_box(bpy, "Robe_Lower",
                        (waist_w + off * 2, td * 0.95 + off * 2, lower_h),
                        (0, 0, hip_z + lower_h / 2))
    parts.append(lower)

    # Skirt (cone widening from waist to ankles)
    skirt_h = leg_len * 0.85
    skirt_bottom_r = hw + 0.15
    skirt = _create_cone(bpy, "Robe_Skirt",
                         r_bottom=skirt_bottom_r, r_top=waist_half_w + off,
                         depth=skirt_h,
                         location=(0, 0, hip_z - skirt_h / 2),
                         segments=12)
    parts.append(skirt)

    # Shoulder covers + wide sleeves
    arm_z = chest_z - 0.06
    for side, x_sign in [("L", 1), ("R", -1)]:
        sx = x_sign * shoulder_x

        # Shoulder cover
        bridge_w = shoulder_x - sw + 0.03
        bridge = _create_box(bpy, f"Robe_Shoulder_{side}",
                             (bridge_w + off, td * 0.85 + off, 0.08),
                             (x_sign * (sw + bridge_w / 2 - 0.01), 0, chest_z - 0.03))
        parts.append(bridge)

        # Wide sleeve (longer and flared)
        sleeve_len = arm_len * 0.7
        sleeve = _create_cone(bpy, f"Robe_Sleeve_{side}",
                              r_bottom=0.055 * lt + off, r_top=0.07 * lt + off,
                              depth=sleeve_len,
                              location=(sx, 0, arm_z - sleeve_len / 2), segments=10)
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
