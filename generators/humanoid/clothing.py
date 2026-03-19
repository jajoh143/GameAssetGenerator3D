"""Low-poly clothing generation for humanoid characters.

Uses BVH surface projection inspired by MB-Lab's proxy engine:
1. Build a clothing template mesh using ring-based construction
   (same technique as the body base mesh)
2. Project clothing vertices onto the body surface using BVH tree
3. Offset outward along surface normals for clothing thickness

This replaces the old Skin-modifier + bisect approach, giving better
fit and predictable topology.

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

import math

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

# Ring vertex count (matches base_mesh.py)
RING_VERTS = 8


# ─── Ring-based clothing template builders ─────────────────────────────────

def _make_ring(bm, center, rx, ry, n=RING_VERTS):
    """Create a ring of vertices in an elliptical cross-section."""
    verts = []
    cx, cy, cz = center
    for i in range(n):
        angle = 2 * math.pi * i / n
        lx = cx + rx * math.sin(angle)
        ly = cy - ry * math.cos(angle)
        verts.append(bm.verts.new((lx, ly, cz)))
    return verts


def _bridge_rings(bm, ring_a, ring_b):
    """Connect two rings with quad faces."""
    n = len(ring_a)
    assert len(ring_b) == n
    faces = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])
        faces.append(f)
    return faces


def _cap_ring(bm, ring, inward=True):
    """Close an open ring end with a triangle fan.

    Creates a center vertex at the ring centroid and fans triangles
    outward to each edge.  This eliminates open-edge gaps at clothing
    hems, sleeve cuffs, and trouser bottoms.

    Args:
        bm: bmesh instance
        ring: list of bmesh Vert objects forming the open loop
        inward: if True the fan normal points inward (use for hem/cuff
                ends that face downward); False reverses the winding for
                upward-facing ends (e.g. waistbands, collar tops).
    """
    cx = sum(v.co.x for v in ring) / len(ring)
    cy = sum(v.co.y for v in ring) / len(ring)
    cz = sum(v.co.z for v in ring) / len(ring)
    center = bm.verts.new((cx, cy, cz))
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        if inward:
            bm.faces.new([ring[j], ring[i], center])
        else:
            bm.faces.new([ring[i], ring[j], center])
    return center


def _project_to_body(clothing_bm, body_obj, offset=0.008):
    """Project clothing vertices onto body surface using BVH tree.

    For each clothing vertex, finds the nearest point on the body surface
    and snaps the vertex to that point + offset along the surface normal.

    Args:
        clothing_bm: bmesh with clothing template geometry
        body_obj: Blender object with body mesh
        offset: distance to push outward along normals
    """
    import bmesh
    from mathutils.bvhtree import BVHTree

    # Build BVH from body mesh
    body_bm = bmesh.new()
    body_bm.from_mesh(body_obj.data)
    body_bm.transform(body_obj.matrix_world)
    bmesh.ops.recalc_face_normals(body_bm, faces=body_bm.faces[:])
    bvh = BVHTree.FromBMesh(body_bm)

    # Project each clothing vertex
    clothing_bm.verts.ensure_lookup_table()
    for v in clothing_bm.verts:
        location, normal, index, distance = bvh.find_nearest(v.co)
        if location is not None:
            v.co = location + normal * offset

    body_bm.free()


def _clothing_bmesh_to_object(bm, name):
    """Convert clothing bmesh to a Blender object."""
    import bpy
    import bmesh as bmesh_mod

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Smooth shading
    bpy.ops.object.shade_smooth()

    return obj


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


def _get_body_object():
    """Find the body mesh object in the current scene."""
    import bpy
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and "Humanoid_Body" in obj.name:
            return obj
    return None


# ─── Clothing template builders ────────────────────────────────────────────

def _build_tshirt_template(cfg):
    """Build t-shirt template: torso tube + separate sleeve tubes.

    Sleeves are independent tubes that overlap with the torso at the
    shoulder area, avoiding the broken geometry from bridging centered
    torso rings to offset arm rings.
    """
    import bmesh

    bm = bmesh.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    scale = 1.05
    shirt_hem_z = hip_z + torso_len * 0.25

    # Torso tube
    torso_specs = [
        (shirt_hem_z,   hw * 0.78 * scale, td * 0.43 * scale),
        (waist_z,       sw * 0.65 * scale, td * 0.40 * scale),
        (lower_chest_z, sw * 0.90 * scale, td * 0.54 * scale),
        (chest_z,       sw * 1.05 * scale, td * 0.58 * scale),
    ]
    torso_rings = []
    for z, rx, ry in torso_specs:
        ring = _make_ring(bm, (0, 0, z), rx, ry)
        torso_rings.append(ring)
    for i in range(len(torso_rings) - 1):
        _bridge_rings(bm, torso_rings[i], torso_rings[i + 1])
    # Cap the shirt hem (bottom open edge — faces downward)
    _cap_ring(bm, torso_rings[0], inward=True)

    # Sleeve tubes — separate from torso, overlapping at shoulder height
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02  # start slightly inside chest for overlap
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len

    for side_sign in [1, -1]:
        sx = side_sign * shoulder_x
        sleeve_specs = [
            (arm_top_z,                       0.078 * lt * scale, 0.068 * lt * scale),
            (arm_top_z - upper_arm_len * 0.35, 0.072 * lt * scale, 0.064 * lt * scale),
            (arm_top_z - upper_arm_len * 0.70, 0.062 * lt * scale, 0.058 * lt * scale),
            (elbow_z,                         0.054 * lt * scale, 0.052 * lt * scale),
        ]
        sleeve_rings = []
        for z, rx, ry in sleeve_specs:
            ring = _make_ring(bm, (sx, 0, z), rx, ry)
            sleeve_rings.append(ring)
        for i in range(len(sleeve_rings) - 1):
            _bridge_rings(bm, sleeve_rings[i], sleeve_rings[i + 1])
        # Cap the sleeve cuff (open bottom of each sleeve)
        _cap_ring(bm, sleeve_rings[-1], inward=True)

    return bm


def _build_jacket_template(cfg):
    """Build jacket template: torso + full arm tubes + collar."""
    import bmesh

    bm = bmesh.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]
    neck_len = cfg["neck_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    scale = 1.08

    torso_specs = [
        (hip_z,         hw + 0.05 * scale, td * 0.52 * scale),
        (lower_waist_z, hw * 0.80 * scale, td * 0.44 * scale),
        (waist_z,       sw * 0.65 * scale, td * 0.40 * scale),
        (lower_chest_z, sw * 0.90 * scale, td * 0.54 * scale),
        (chest_z,       sw * 1.05 * scale, td * 0.58 * scale),
    ]
    torso_rings = []
    for z, rx, ry in torso_specs:
        ring = _make_ring(bm, (0, 0, z), rx, ry)
        torso_rings.append(ring)
    for i in range(len(torso_rings) - 1):
        _bridge_rings(bm, torso_rings[i], torso_rings[i + 1])
    # Cap jacket hem (bottom open edge)
    _cap_ring(bm, torso_rings[0], inward=True)

    # Collar
    collar_ring = _make_ring(bm, (0, 0, chest_z + neck_len * 0.3),
                             0.07 * lt, 0.07 * lt)
    _bridge_rings(bm, torso_rings[-1], collar_ring)
    # Cap collar top (faces upward)
    _cap_ring(bm, collar_ring, inward=False)

    # Separate arm tubes
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    for side_sign in [1, -1]:
        sx = side_sign * shoulder_x
        arm_specs = [
            (arm_top_z,                       0.078 * lt * scale, 0.068 * lt * scale),
            (arm_top_z - upper_arm_len * 0.5, 0.068 * lt * scale, 0.062 * lt * scale),
            (elbow_z,                         0.054 * lt * scale, 0.054 * lt * scale),
            (elbow_z - lower_arm_len * 0.3,   0.058 * lt * scale, 0.054 * lt * scale),
            (wrist_z,                         0.044 * lt * scale, 0.040 * lt * scale),
        ]
        arm_rings = []
        for z, rx, ry in arm_specs:
            ring = _make_ring(bm, (sx, 0, z), rx, ry)
            arm_rings.append(ring)
        for i in range(len(arm_rings) - 1):
            _bridge_rings(bm, arm_rings[i], arm_rings[i + 1])
        # Cap wrist cuff (open bottom)
        _cap_ring(bm, arm_rings[-1], inward=True)

    return bm


def _build_pants_template(cfg):
    """Build pants template: waist tube + separate leg tubes.

    Leg tubes overlap with the waist tube at the hip area rather
    than bridging between incompatible centered/offset rings.
    """
    import bmesh

    bm = bmesh.new()

    hw = cfg["hip_width"]
    sw = cfg["shoulder_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    knee_z = foot_top + leg_len * 0.48

    scale = 1.05

    # Waistband / hip section
    belt_z = hip_z + torso_len * 0.12
    crotch_z = hip_z - (hip_z - knee_z) * 0.15  # where waist ends, legs begin

    waist_specs = [
        (lower_waist_z, hw * 0.80 * scale, td * 0.44 * scale),
        (belt_z,        hw * 0.90 * scale, td * 0.48 * scale),
        (hip_z,         (hw + 0.05) * scale, td * 0.52 * scale),
        (crotch_z,      (hw + 0.04) * scale, td * 0.50 * scale),
    ]
    waist_rings = []
    for z, rx, ry in waist_specs:
        ring = _make_ring(bm, (0, 0, z), rx, ry)
        waist_rings.append(ring)
    for i in range(len(waist_rings) - 1):
        _bridge_rings(bm, waist_rings[i], waist_rings[i + 1])
    # Cap waistband top (faces upward)
    _cap_ring(bm, waist_rings[0], inward=False)

    # Separate leg tubes — overlap with waist at hip_z
    thigh_z = hip_z - (hip_z - knee_z) * 0.35
    calf_z = knee_z - (knee_z - foot_top) * 0.30

    for side_sign in [1, -1]:
        x = side_sign * hw
        leg_specs = [
            (hip_z,    0.112 * lt * scale, 0.100 * lt * scale),
            (thigh_z,  0.115 * lt * scale, 0.100 * lt * scale),
            (knee_z,   0.078 * lt * scale, 0.076 * lt * scale),
            (calf_z,   0.085 * lt * scale, 0.078 * lt * scale),
            (foot_top, 0.062 * lt * scale, 0.060 * lt * scale),
        ]
        leg_rings = []
        for z, rx, ry in leg_specs:
            ring = _make_ring(bm, (x, 0, z), rx, ry)
            leg_rings.append(ring)
        for i in range(len(leg_rings) - 1):
            _bridge_rings(bm, leg_rings[i], leg_rings[i + 1])
        # Cap trouser cuff (open bottom — ankle hem)
        _cap_ring(bm, leg_rings[-1], inward=True)

    return bm


def _build_shorts_template(cfg):
    """Build shorts template: waist tube + short separate leg tubes."""
    import bmesh

    bm = bmesh.new()

    hw = cfg["hip_width"]
    sw = cfg["shoulder_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    knee_z = foot_top + leg_len * 0.48

    scale = 1.06

    belt_z = hip_z + torso_len * 0.12
    crotch_z = hip_z - (hip_z - knee_z) * 0.15

    waist_specs = [
        (lower_waist_z, hw * 0.80 * scale, td * 0.44 * scale),
        (belt_z,        hw * 0.90 * scale, td * 0.48 * scale),
        (hip_z,         (hw + 0.05) * scale, td * 0.52 * scale),
        (crotch_z,      (hw + 0.04) * scale, td * 0.50 * scale),
    ]
    waist_rings = []
    for z, rx, ry in waist_specs:
        ring = _make_ring(bm, (0, 0, z), rx, ry)
        waist_rings.append(ring)
    for i in range(len(waist_rings) - 1):
        _bridge_rings(bm, waist_rings[i], waist_rings[i + 1])
    # Cap shorts waistband top
    _cap_ring(bm, waist_rings[0], inward=False)

    # Short leg tubes
    thigh_z = hip_z - (hip_z - knee_z) * 0.35

    for side_sign in [1, -1]:
        x = side_sign * hw
        leg_specs = [
            (hip_z,    0.112 * lt * scale, 0.100 * lt * scale),
            (thigh_z,  0.115 * lt * scale, 0.100 * lt * scale),
            (knee_z,   0.082 * lt * scale, 0.078 * lt * scale),
        ]
        leg_rings = []
        for z, rx, ry in leg_specs:
            ring = _make_ring(bm, (x, 0, z), rx, ry)
            leg_rings.append(ring)
        for i in range(len(leg_rings) - 1):
            _bridge_rings(bm, leg_rings[i], leg_rings[i + 1])
        # Cap shorts leg hem (open bottom of each leg)
        _cap_ring(bm, leg_rings[-1], inward=True)

    return bm


def _build_armor_template(cfg):
    """Build armor template: thick chest plate with separate shoulder pads."""
    import bmesh

    bm = bmesh.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    scale = 1.12

    torso_specs = [
        (hip_z,         hw + 0.05 * scale, td * 0.52 * scale),
        (lower_waist_z, hw * 0.80 * scale, td * 0.44 * scale),
        (waist_z,       sw * 0.65 * scale, td * 0.40 * scale),
        (lower_chest_z, sw * 0.90 * scale, td * 0.54 * scale),
        (chest_z,       sw * 1.05 * scale, td * 0.58 * scale),
    ]
    torso_rings = []
    for z, rx, ry in torso_specs:
        ring = _make_ring(bm, (0, 0, z), rx, ry)
        torso_rings.append(ring)
    for i in range(len(torso_rings) - 1):
        _bridge_rings(bm, torso_rings[i], torso_rings[i + 1])
    # Cap armor chest-plate bottom hem
    _cap_ring(bm, torso_rings[0], inward=True)

    # Shoulder pads as separate tubes
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02

    for side_sign in [1, -1]:
        sx = side_sign * shoulder_x
        pad_specs = [
            (arm_top_z,        0.090 * lt * scale, 0.080 * lt * scale),
            (arm_top_z - 0.10, 0.078 * lt * scale, 0.068 * lt * scale),
        ]
        pad_rings = []
        for z, rx, ry in pad_specs:
            ring = _make_ring(bm, (sx, 0, z), rx, ry)
            pad_rings.append(ring)
        for i in range(len(pad_rings) - 1):
            _bridge_rings(bm, pad_rings[i], pad_rings[i + 1])
        # Cap shoulder pad bottom
        _cap_ring(bm, pad_rings[-1], inward=True)

    return bm


def _build_robe_template(cfg):
    """Build robe template: torso + skirt + separate sleeve tubes."""
    import bmesh

    bm = bmesh.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    scale = 1.06

    # Upper body + skirt as one continuous tube
    body_specs = [
        (foot_top + 0.10,  hw + 0.18,         td * 0.65),   # skirt bottom
        (hip_z * 0.7,      hw + 0.12,         td * 0.60),   # skirt mid
        (hip_z,            hw + 0.06,         td * 0.55),   # hip
        (lower_waist_z,    hw * 0.80 * scale, td * 0.44 * scale),
        (waist_z,          sw * 0.65 * scale, td * 0.40 * scale),
        (lower_chest_z,    sw * 0.90 * scale, td * 0.54 * scale),
        (chest_z,          sw * 1.05 * scale, td * 0.58 * scale),
    ]
    body_rings = []
    for z, rx, ry in body_specs:
        ring = _make_ring(bm, (0, 0, z), rx, ry)
        body_rings.append(ring)
    for i in range(len(body_rings) - 1):
        _bridge_rings(bm, body_rings[i], body_rings[i + 1])
    # Cap robe skirt hem (bottom open edge)
    _cap_ring(bm, body_rings[0], inward=True)

    # Separate sleeve tubes
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    forearm_z = elbow_z - lower_arm_len * 0.3

    for side_sign in [1, -1]:
        sx = side_sign * shoulder_x
        arm_specs = [
            (arm_top_z,                       0.078 * lt * scale, 0.070 * lt * scale),
            (arm_top_z - upper_arm_len * 0.5, 0.070 * lt * scale, 0.064 * lt * scale),
            (elbow_z,                         0.058 * lt * scale, 0.058 * lt * scale),
            (forearm_z,                       0.060 * lt * scale, 0.056 * lt * scale),
        ]
        arm_rings = []
        for z, rx, ry in arm_specs:
            ring = _make_ring(bm, (sx, 0, z), rx, ry)
            arm_rings.append(ring)
        for i in range(len(arm_rings) - 1):
            _bridge_rings(bm, arm_rings[i], arm_rings[i + 1])
        # Cap robe sleeve end
        _cap_ring(bm, arm_rings[-1], inward=True)

    return bm


# ─── Clothing builders (public interface) ──────────────────────────────────

def _build_clothing_piece(cfg, name, template_fn, color, offset=0.008,
                          roughness=0.85):
    """Build a clothing piece using template + BVH projection.

    Args:
        cfg: body config dict
        name: clothing object name
        template_fn: function that returns a bmesh template
        color: RGBA tuple
        offset: normal offset distance
        roughness: material roughness

    Returns:
        Blender object with material applied.
    """
    bm = template_fn(cfg)

    # Get the body object for projection
    body_obj = _get_body_object()
    if body_obj is not None:
        _project_to_body(bm, body_obj, offset=offset)

    obj = _clothing_bmesh_to_object(bm, name)
    bm.free()

    _apply_clothing_material(obj, color, roughness)
    return obj


def _build_tshirt(cfg, color):
    """T-shirt: torso + upper arms (sleeves to elbow)."""
    obj = _build_clothing_piece(cfg, "TShirt", _build_tshirt_template,
                                color, offset=0.008)
    return [(obj, "Spine")]


def _build_jacket(cfg, color):
    """Jacket: torso + full arms + collar."""
    obj = _build_clothing_piece(cfg, "Jacket", _build_jacket_template,
                                color, offset=0.012)
    return [(obj, "Spine")]


def _build_pants(cfg, color):
    """Pants: waist to ankles."""
    obj = _build_clothing_piece(cfg, "Pants", _build_pants_template,
                                color, offset=0.008)
    return [(obj, "Hips")]


def _build_shorts(cfg, color):
    """Shorts: waist to knee."""
    obj = _build_clothing_piece(cfg, "Shorts", _build_shorts_template,
                                color, offset=0.010)
    return [(obj, "Hips")]


def _build_armor(cfg, color):
    """Armor: thick chest plate with shoulder pads."""
    obj = _build_clothing_piece(cfg, "Armor", _build_armor_template,
                                color, offset=0.018, roughness=0.4)
    return [(obj, "Spine")]


def _build_robe(cfg, color):
    """Robe: full torso + sleeves + long skirt."""
    obj = _build_clothing_piece(cfg, "Robe", _build_robe_template,
                                color, offset=0.010)
    return [(obj, "Spine")]


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
