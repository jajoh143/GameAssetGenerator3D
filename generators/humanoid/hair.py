"""Low-poly hair generation for humanoid characters.

Each hair style is built from simple primitives (boxes, spheres, cylinders)
positioned relative to the head center and radius. Hair is returned as a list
of Blender objects that get joined into the body mesh.

Available styles:
    - "buzzed":  Thin skullcap hugging the head
    - "short":   Slightly raised cap with volume on top
    - "spiky":   Several extruded spike-like cones on top
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


# ─── Hair style builders ───────────────────────────────────────────────────

def build_buzzed(head_z, head_r):
    """Thin skullcap that hugs the top of the head."""
    import bpy
    parts = []
    cap = _create_sphere(bpy, "Hair_Buzzed", head_r * 1.04,
                         (0, 0, head_z + head_r * 0.25),
                         segments=10, rings=5)
    cap.scale = (1.0, 1.0, 0.45)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.transform_apply(scale=True)
    parts.append(cap)
    return parts


def build_short(head_z, head_r):
    """Short hair with volume on top — cap + slight side coverage."""
    import bpy
    parts = []
    top = _create_sphere(bpy, "Hair_Short_Top", head_r * 1.10,
                         (0, 0, head_z + head_r * 0.30),
                         segments=10, rings=5)
    top.scale = (1.05, 1.0, 0.5)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.transform_apply(scale=True)
    parts.append(top)

    back = _create_box(bpy, "Hair_Short_Back",
                       (head_r * 1.8, head_r * 0.5, head_r * 0.7),
                       (0, -head_r * 0.45, head_z + head_r * 0.40))
    parts.append(back)
    return parts


def build_spiky(head_z, head_r):
    """Multiple low-poly cones sticking up from the top of the head."""
    import bpy
    parts = []

    cap = _create_sphere(bpy, "Hair_Spiky_Base", head_r * 1.06,
                         (0, 0, head_z + head_r * 0.30),
                         segments=10, rings=4)
    cap.scale = (1.0, 1.0, 0.4)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.transform_apply(scale=True)
    parts.append(cap)

    spike_layout = [
        (0.0,    0.0,    0,    0),      # center
        (0.55,   0.0,   15,    0),      # right
        (-0.55,  0.0,  -15,    0),      # left
        (0.0,    0.45,   0,  -15),      # front
        (0.0,   -0.45,   0,   15),      # back
        (0.35,   0.35,  10,  -10),      # front-right
        (-0.35,  0.35, -10,  -10),      # front-left
    ]

    spike_h = head_r * 0.55
    spike_r = head_r * 0.12

    for i, (xo, yo, tilt_x, tilt_y) in enumerate(spike_layout):
        x = xo * head_r
        y = yo * head_r
        z = head_z + head_r * 0.95 + spike_h / 2

        spike = _create_cone(bpy, f"Hair_Spike_{i}", spike_r, spike_h,
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

    top = _create_sphere(bpy, "Hair_Long_Top", head_r * 1.12,
                         (0, 0, head_z + head_r * 0.30),
                         segments=10, rings=5)
    top.scale = (1.05, 1.05, 0.5)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.transform_apply(scale=True)
    parts.append(top)

    curtain_h = head_r * 2.8
    curtain_w = head_r * 0.35
    for side, x_sign in [("L", 1), ("R", -1)]:
        curtain = _create_box(
            bpy, f"Hair_Long_Side_{side}",
            (curtain_w, head_r * 0.8, curtain_h),
            (x_sign * head_r * 0.85, -head_r * 0.1,
             head_z - curtain_h / 2 + head_r * 0.55),
        )
        parts.append(curtain)

    back_h = head_r * 3.5
    back = _create_box(bpy, "Hair_Long_Back",
                       (head_r * 1.6, head_r * 0.4, back_h),
                       (0, -head_r * 0.65,
                        head_z - back_h / 2 + head_r * 0.65))
    parts.append(back)
    return parts


def build_mohawk(head_z, head_r):
    """Tall central ridge from front to back of head."""
    import bpy
    parts = []

    ridge_count = 5
    ridge_height = head_r * 0.9
    ridge_width = head_r * 0.2
    ridge_total_len = head_r * 1.8
    step = ridge_total_len / ridge_count

    for i in range(ridge_count):
        y = head_r * 0.5 - i * step
        t = abs(i - ridge_count / 2) / (ridge_count / 2)
        h = ridge_height * (1.0 - 0.3 * t)
        z = head_z + head_r * 0.9 + h / 2

        segment = _create_box(
            bpy, f"Hair_Mohawk_{i}",
            (ridge_width, step * 0.9, h),
            (0, y, z),
        )
        parts.append(segment)

    for side, x_sign in [("L", 1), ("R", -1)]:
        side_cap = _create_sphere(
            bpy, f"Hair_Mohawk_Side_{side}",
            head_r * 1.02,
            (x_sign * head_r * 0.15, 0, head_z + head_r * 0.25),
            segments=8, rings=4,
        )
        side_cap.scale = (0.5, 0.9, 0.4)
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
    """Create hair geometry and return the list of objects.

    Args:
        head_z: Z position of head center.
        head_r: Head sphere radius.
        style: Hair style name (or "none" for bald).
        color: RGBA tuple or named color string. Defaults to "dark_brown".

    Returns:
        List of Blender objects (empty if style is "none").
    """
    import bpy

    if style == "none":
        return []

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

    return parts
