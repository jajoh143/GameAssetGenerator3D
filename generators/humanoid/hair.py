"""Low-poly hair generation for humanoid characters.

Each hair style is built from simple primitives (boxes, spheres, cylinders)
positioned relative to the head center and radius. Hair is returned as a
single joined Blender object that gets parented to the Head bone so it
moves with the head.

Available styles:
    - "buzzed":  Thin skullcap hugging the head
    - "short":   Slightly raised cap with volume on top
    - "spiky":   Dense array of extruded spike-like cones on top
    - "long":    Flows down past the shoulders
    - "mohawk":  Tall central ridge from forehead to nape

Data constants (HAIR_STYLES, HAIR_COLORS) are importable without bpy.
Builder functions and create_hair() require Blender's Python environment.
"""

import math

# ─── Data constants (no bpy dependency) ────────────────────────────────────

HAIR_STYLES = ("none", "buzzed", "short", "spiky", "long", "mohawk")

# Named hair color palettes (RGBA)
HAIR_COLORS = {
    "black":     (0.05, 0.04, 0.04, 1.0),
    "dark_brown": (0.18, 0.10, 0.06, 1.0),
    "brown":     (0.30, 0.18, 0.08, 1.0),
    "auburn":    (0.42, 0.16, 0.08, 1.0),
    "red":       (0.55, 0.12, 0.06, 1.0),
    "blonde":    (0.72, 0.58, 0.30, 1.0),
    "platinum":  (0.85, 0.82, 0.72, 1.0),
    "white":     (0.90, 0.88, 0.85, 1.0),
    "grey":      (0.50, 0.48, 0.46, 1.0),
    # Fantasy
    "blue":      (0.15, 0.25, 0.65, 1.0),
    "green":     (0.12, 0.50, 0.18, 1.0),
    "purple":    (0.40, 0.12, 0.55, 1.0),
    "pink":      (0.75, 0.30, 0.50, 1.0),
}


def get_hair_style_names():
    """Return list of available hair style names."""
    return list(HAIR_STYLES)


def get_hair_color_names():
    """Return sorted list of available hair color names."""
    return sorted(HAIR_COLORS.keys())


# ─── Blender geometry helpers (bpy imported at call time) ──────────────────

def _create_box(bpy, name, size, location):
    """Create a box mesh at the given location."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    bpy.ops.object.transform_apply(scale=True)
    return obj


def _create_sphere(bpy, name, radius, location, segments=8, rings=6):
    """Create a low-poly sphere."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings,
        radius=radius, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_cone(bpy, name, radius, depth, location, segments=6):
    """Create a low-poly cone (used for spikes)."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments, radius1=radius, radius2=0,
        depth=depth, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _join_parts(bpy, parts):
    """Join a list of objects into one mesh."""
    if not parts:
        return None
    if len(parts) == 1:
        parts[0].name = "Hair"
        return parts[0]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = "Hair"
    return result


# ─── Hair style builders ───────────────────────────────────────────────────

def build_buzzed(head_z, head_r):
    """Thin skullcap that hugs the top and sides of the head."""
    import bpy
    parts = []

    # Main cap — centered on the upper head, wrapping sides
    # head_z is the center of the head; brow is at ~head_z + 0.2*head_r
    cap_z = head_z + head_r * 0.30
    cap = _create_sphere(bpy, "Hair_Buzzed", head_r * 1.06,
                         (0, head_r * 0.05, cap_z),
                         segments=12, rings=6)
    cap.scale = (1.0, 1.0, 0.55)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.transform_apply(scale=True)
    parts.append(cap)

    # Side coverage wrapping around temples
    for side, x_sign in [("L", 1), ("R", -1)]:
        side_cap = _create_sphere(
            bpy, f"Hair_Buzzed_Side_{side}",
            head_r * 0.90,
            (x_sign * head_r * 0.45, head_r * 0.08, head_z + head_r * 0.10),
            segments=8, rings=4,
        )
        side_cap.scale = (0.55, 0.85, 0.65)
        bpy.context.view_layer.objects.active = side_cap
        bpy.ops.object.transform_apply(scale=True)
        parts.append(side_cap)

    return parts


def build_short(head_z, head_r):
    """Short hair with volume — wraps from forehead over top and down sides."""
    import bpy
    parts = []

    # Top section — sits on the upper head from forehead to crown
    top_z = head_z + head_r * 0.35
    top = _create_sphere(bpy, "Hair_Short_Top", head_r * 1.10,
                         (0, head_r * 0.05, top_z),
                         segments=12, rings=6)
    top.scale = (1.05, 1.02, 0.55)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.transform_apply(scale=True)
    parts.append(top)

    # Back section — covers the back of the head down to just above neck
    back_z = head_z + head_r * 0.10
    back = _create_box(bpy, "Hair_Short_Back",
                       (head_r * 1.7, head_r * 0.50, head_r * 1.0),
                       (0, head_r * 0.50, back_z))
    parts.append(back)

    # Side sections — wrap around the temples and above ears
    for side, x_sign in [("L", 1), ("R", -1)]:
        side_part = _create_sphere(
            bpy, f"Hair_Short_Side_{side}",
            head_r * 0.85,
            (x_sign * head_r * 0.55, head_r * 0.10, head_z + head_r * 0.15),
            segments=8, rings=4,
        )
        side_part.scale = (0.50, 0.85, 0.65)
        bpy.context.view_layer.objects.active = side_part
        bpy.ops.object.transform_apply(scale=True)
        parts.append(side_part)

    # Fringe/bangs across forehead
    fringe_z = head_z + head_r * 0.40
    fringe = _create_box(bpy, "Hair_Short_Fringe",
                         (head_r * 1.5, head_r * 0.25, head_r * 0.25),
                         (0, -(head_r * 0.65), fringe_z))
    parts.append(fringe)

    return parts


def build_spiky(head_z, head_r):
    """Dense array of spiky cones radiating from the top of the head."""
    import bpy
    parts = []

    # Base cap — wrapping upper head
    cap_z = head_z + head_r * 0.30
    cap = _create_sphere(bpy, "Hair_Spiky_Base", head_r * 1.08,
                         (0, head_r * 0.05, cap_z),
                         segments=12, rings=6)
    cap.scale = (1.05, 1.02, 0.55)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.transform_apply(scale=True)
    parts.append(cap)

    # Dense spike layout — more spikes, varied heights
    spike_layout = [
        # (x_offset, y_offset, tilt_x_deg, tilt_y_deg, height_mult)
        # Center spikes (tallest)
        (0.0,    0.0,    0,    0,   1.0),
        (0.0,    0.25,   0,   -8,   0.95),
        (0.0,   -0.25,   0,    8,   0.9),
        # Right side
        (0.45,   0.0,   18,    0,   0.85),
        (0.45,   0.25,  16,   -8,   0.8),
        (0.45,  -0.25,  16,    8,   0.75),
        (0.7,    0.0,   25,    0,   0.7),
        # Left side
        (-0.45,  0.0,  -18,    0,   0.85),
        (-0.45,  0.25, -16,   -8,   0.8),
        (-0.45, -0.25, -16,    8,   0.75),
        (-0.7,   0.0,  -25,    0,   0.7),
        # Front
        (0.0,    0.5,    0,  -18,   0.85),
        (0.3,    0.45,  12,  -15,   0.75),
        (-0.3,   0.45, -12,  -15,   0.75),
        # Back
        (0.0,   -0.5,    0,   18,   0.8),
        (0.3,   -0.45,  12,   15,   0.7),
        (-0.3,  -0.45, -12,   15,   0.7),
        # Diagonal fills
        (0.25,   0.35,   8,  -10,   0.88),
        (-0.25,  0.35,  -8,  -10,   0.88),
        (0.25,  -0.35,   8,   10,   0.82),
        (-0.25, -0.35,  -8,   10,   0.82),
    ]

    spike_h = head_r * 0.7
    spike_r = head_r * 0.11

    for i, (xo, yo, tilt_x, tilt_y, h_mult) in enumerate(spike_layout):
        x = xo * head_r
        y = yo * head_r
        h = spike_h * h_mult
        z = head_z + head_r * 0.72 + h / 2

        spike = _create_cone(bpy, f"Hair_Spike_{i}", spike_r, h,
                             (x, y, z), segments=5)
        spike.rotation_euler = (math.radians(tilt_y), math.radians(tilt_x), 0)
        bpy.context.view_layer.objects.active = spike
        bpy.ops.object.transform_apply(rotation=True)
        parts.append(spike)

    return parts


def build_long(head_z, head_r):
    """Long hair flowing down past the shoulders."""
    import bpy
    parts = []

    # Top cap wrapping upper head
    top_z = head_z + head_r * 0.35
    top = _create_sphere(bpy, "Hair_Long_Top", head_r * 1.12,
                         (0, head_r * 0.05, top_z),
                         segments=12, rings=6)
    top.scale = (1.06, 1.06, 0.55)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.transform_apply(scale=True)
    parts.append(top)

    # Side curtains flowing down
    curtain_h = head_r * 2.8
    curtain_w = head_r * 0.4
    for side, x_sign in [("L", 1), ("R", -1)]:
        curtain = _create_box(
            bpy, f"Hair_Long_Side_{side}",
            (curtain_w, head_r * 0.85, curtain_h),
            (x_sign * head_r * 0.80, head_r * 0.1,
             head_z - curtain_h / 2 + head_r * 0.50),
        )
        parts.append(curtain)

    # Back section flowing down
    back_h = head_r * 3.5
    back = _create_box(bpy, "Hair_Long_Back",
                       (head_r * 1.6, head_r * 0.45, back_h),
                       (0, head_r * 0.55,
                        head_z - back_h / 2 + head_r * 0.60))
    parts.append(back)

    # Fringe / bangs across forehead
    fringe_z = head_z + head_r * 0.40
    fringe = _create_box(bpy, "Hair_Long_Fringe",
                         (head_r * 1.5, head_r * 0.3, head_r * 0.30),
                         (0, -(head_r * 0.65), fringe_z))
    parts.append(fringe)

    return parts


def build_mohawk(head_z, head_r):
    """Tall central ridge from front to back of head."""
    import bpy
    parts = []

    ridge_count = 7
    ridge_height = head_r * 1.0
    ridge_width = head_r * 0.22
    ridge_total_len = head_r * 2.0
    step = ridge_total_len / ridge_count

    for i in range(ridge_count):
        y = -(head_r * 0.6) + i * step
        t = abs(i - ridge_count / 2) / (ridge_count / 2)
        h = ridge_height * (1.0 - 0.3 * t)
        z = head_z + head_r * 0.72 + h / 2

        segment = _create_box(
            bpy, f"Hair_Mohawk_{i}",
            (ridge_width, step * 0.9, h),
            (0, y, z),
        )
        parts.append(segment)

    # Side buzz underneath the mohawk
    for side, x_sign in [("L", 1), ("R", -1)]:
        side_cap = _create_sphere(
            bpy, f"Hair_Mohawk_Side_{side}",
            head_r * 1.03,
            (x_sign * head_r * 0.40, head_r * 0.05, head_z + head_r * 0.20),
            segments=8, rings=4,
        )
        side_cap.scale = (0.35, 0.85, 0.50)
        bpy.context.view_layer.objects.active = side_cap
        bpy.ops.object.transform_apply(scale=True)
        parts.append(side_cap)

    return parts


# ─── Style dispatch ────────────────────────────────────────────────────────

HAIR_BUILDERS = {
    "buzzed":  build_buzzed,
    "short":   build_short,
    "spiky":   build_spiky,
    "long":    build_long,
    "mohawk":  build_mohawk,
}


def create_hair(head_z, head_r, style="short", color=None):
    """Create hair geometry and return a single joined object.

    Args:
        head_z: Z position of head center.
        head_r: Head sphere radius.
        style: Hair style name (or "none" for bald).
        color: RGBA tuple or named color string. Defaults to "dark_brown".

    Returns:
        A single Blender object (or None if style is "none").
    """
    import bpy

    if style == "none":
        return None

    if style not in HAIR_BUILDERS:
        raise ValueError(f"Unknown hair style '{style}'. Available: {list(HAIR_STYLES)}")

    # Resolve color
    if color is None:
        rgba = HAIR_COLORS["dark_brown"]
    elif isinstance(color, str):
        if color not in HAIR_COLORS:
            raise ValueError(f"Unknown hair color '{color}'. Available: {get_hair_color_names()}")
        rgba = HAIR_COLORS[color]
    else:
        rgba = tuple(color)

    # Build the hair parts
    parts = HAIR_BUILDERS[style](head_z, head_r)

    # Apply hair material to all parts
    mat = bpy.data.materials.new(name="Hair_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.9
    for part in parts:
        part.data.materials.append(mat)

    # Join into a single hair object
    hair_obj = _join_parts(bpy, parts)
    return hair_obj
