"""Low-poly humanoid mesh construction.

Builds the body using Blender's Skin modifier on a stick-figure skeleton.
The Skin modifier generates smooth, organic geometry from vertices and edges,
with per-vertex radii controlling body thickness at each joint. This produces
natural shoulder rounding, smooth torso tapering, and subtle muscle definition
without stacking primitives.

The skeleton includes intermediate vertices for muscle bulges (deltoid, bicep,
forearm, thigh, calf) and torso shaping (lower chest, lower waist). A
Subdivision Surface modifier (level 1) is applied on top for additional
smoothing.

The skeleton builder is exposed via build_body_skeleton() so clothing.py can
reuse the same skeleton with inflated radii for perfectly fitting clothing.
"""

import bpy
import math
from mathutils import Vector, Matrix


def _clear_scene():
    """Remove default objects."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def _create_box(name, size, location, scale=(1, 1, 1)):
    """Create a box mesh at the given location."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] * scale[0], size[1] * scale[1], size[2] * scale[2])
    bpy.ops.object.transform_apply(scale=True)
    return obj


def _create_sphere(name, radius, location, segments=12, rings=8):
    """Create a UV sphere."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _join_objects(objects):
    """Join multiple objects into one mesh."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = "Humanoid_Body"
    return result


def _create_hand(name, hand_size, location, side="L"):
    """Create a low-poly mitt-with-thumb hand.

    Builds a flat palm + tapered finger block + separate thumb using
    simple box geometry.  ~24 faces per hand — much more readable as
    a human hand than the old sphere, and lower poly count.

    Args:
        name: object name (e.g. "Hand.L")
        hand_size: base scale factor from config
        location: (x, y, z) wrist attachment point
        side: "L" or "R" — mirrors the thumb on X axis
    """
    import bmesh

    bm = bmesh.new()
    s = hand_size           # base scale
    x0, y0, z0 = location
    sign = 1 if side == "L" else -1

    # Palm dimensions
    palm_w = s * 0.90       # width (X)
    palm_d = s * 0.50       # depth/thickness (Y)
    palm_h = s * 1.0        # height (Z, wrist to finger root)

    # --- Palm (box) ---
    # 8 verts, oriented so Z is along the arm (downward from wrist)
    pw, pd, ph = palm_w / 2, palm_d / 2, palm_h
    palm_verts = [
        bm.verts.new((x0 + sign * (-pw), y0 - pd, z0)),            # 0: top-back-inner
        bm.verts.new((x0 + sign * ( pw), y0 - pd, z0)),            # 1: top-back-outer
        bm.verts.new((x0 + sign * ( pw), y0 + pd, z0)),            # 2: top-front-outer
        bm.verts.new((x0 + sign * (-pw), y0 + pd, z0)),            # 3: top-front-inner
        bm.verts.new((x0 + sign * (-pw * 0.9), y0 - pd * 0.8, z0 - ph)),  # 4: bot-back-inner
        bm.verts.new((x0 + sign * ( pw * 0.9), y0 - pd * 0.8, z0 - ph)),  # 5: bot-back-outer
        bm.verts.new((x0 + sign * ( pw * 0.9), y0 + pd * 0.8, z0 - ph)),  # 6: bot-front-outer
        bm.verts.new((x0 + sign * (-pw * 0.9), y0 + pd * 0.8, z0 - ph)),  # 7: bot-front-inner
    ]
    pv = palm_verts
    # 6 faces for the palm box
    bm.faces.new([pv[0], pv[1], pv[2], pv[3]])  # top
    bm.faces.new([pv[4], pv[7], pv[6], pv[5]])  # bottom
    bm.faces.new([pv[0], pv[3], pv[7], pv[4]])  # inner side
    bm.faces.new([pv[1], pv[5], pv[6], pv[2]])  # outer side
    bm.faces.new([pv[0], pv[4], pv[5], pv[1]])  # back
    bm.faces.new([pv[3], pv[2], pv[6], pv[7]])  # front (palm face)

    # --- Fingers (tapered slab extending from palm bottom) ---
    finger_len = s * 0.80
    ftaper = 0.65           # fingers narrow toward tips
    fz = z0 - ph - finger_len
    fv = [
        pv[4],  # reuse palm bottom verts as finger root
        pv[5],
        pv[6],
        pv[7],
        bm.verts.new((x0 + sign * (-pw * 0.9 * ftaper), y0 - pd * 0.6, fz)),  # 8: tip-back-inner
        bm.verts.new((x0 + sign * ( pw * 0.9 * ftaper), y0 - pd * 0.6, fz)),  # 9: tip-back-outer
        bm.verts.new((x0 + sign * ( pw * 0.9 * ftaper), y0 + pd * 0.6, fz)),  # 10: tip-front-outer
        bm.verts.new((x0 + sign * (-pw * 0.9 * ftaper), y0 + pd * 0.6, fz)),  # 11: tip-front-inner
    ]
    # 5 faces for fingers (top is shared with palm bottom)
    bm.faces.new([fv[4], fv[5], fv[6], fv[7]])  # fingertip cap
    bm.faces.new([fv[0], fv[4], fv[5], fv[1]])  # back
    bm.faces.new([fv[3], fv[2], fv[6], fv[7]])  # front (palm side)
    bm.faces.new([fv[0], fv[3], fv[7], fv[4]])  # inner
    bm.faces.new([fv[1], fv[5], fv[6], fv[2]])  # outer

    # --- Thumb (small tapered box, angled outward) ---
    thumb_len = s * 0.55
    tw, td_t = palm_w * 0.30, palm_d * 0.35
    # Thumb root: inner side of palm, slightly below wrist
    tx_base = x0 + sign * (-pw * 0.7)
    tz_base = z0 - ph * 0.25
    # Thumb tip: angled outward and downward
    tx_tip = x0 + sign * (-pw * 1.35)
    tz_tip = tz_base - thumb_len
    tv = [
        bm.verts.new((tx_base - sign * tw, y0 - td_t, tz_base)),         # 12
        bm.verts.new((tx_base + sign * tw, y0 - td_t, tz_base)),         # 13
        bm.verts.new((tx_base + sign * tw, y0 + td_t, tz_base)),         # 14
        bm.verts.new((tx_base - sign * tw, y0 + td_t, tz_base)),         # 15
        bm.verts.new((tx_tip - sign * tw * 0.6, y0 - td_t * 0.7, tz_tip)),  # 16
        bm.verts.new((tx_tip + sign * tw * 0.6, y0 - td_t * 0.7, tz_tip)),  # 17
        bm.verts.new((tx_tip + sign * tw * 0.6, y0 + td_t * 0.7, tz_tip)),  # 18
        bm.verts.new((tx_tip - sign * tw * 0.6, y0 + td_t * 0.7, tz_tip)),  # 19
    ]
    # 6 faces for the thumb
    bm.faces.new([tv[0], tv[1], tv[2], tv[3]])  # root cap
    bm.faces.new([tv[4], tv[7], tv[6], tv[5]])  # tip cap
    bm.faces.new([tv[0], tv[4], tv[5], tv[1]])  # back
    bm.faces.new([tv[3], tv[2], tv[6], tv[7]])  # front
    bm.faces.new([tv[0], tv[3], tv[7], tv[4]])  # inner
    bm.faces.new([tv[1], tv[5], tv[6], tv[2]])  # outer

    # Build Blender mesh from bmesh
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    return obj


def _apply_material(obj, skin_tone=None):
    """Apply a base material with configurable skin tone."""
    mat = bpy.data.materials.new(name="Humanoid_Base")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        color = skin_tone if skin_tone else (0.65, 0.55, 0.45, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.69
    obj.data.materials.append(mat)


# ─── Skeleton builder (shared with clothing.py) ────────────────────────────

# Vertex name constants for indexing into the skeleton.
# These define which vertices belong to which body region, so clothing
# builders can select subsets of the skeleton.

# Spine: 0-6
V_PELVIS = 0
V_HIP = 1
V_LOWER_WAIST = 2
V_WAIST = 3
V_LOWER_CHEST = 4
V_CHEST = 5
V_NECK = 6

# Left arm: 7-13
V_L_INNER_SHOULDER = 7
V_L_SHOULDER = 8
V_L_DELTOID = 9
V_L_BICEP = 10
V_L_ELBOW = 11
V_L_FOREARM = 12
V_L_WRIST = 13

# Right arm: 14-20
V_R_INNER_SHOULDER = 14
V_R_SHOULDER = 15
V_R_DELTOID = 16
V_R_BICEP = 17
V_R_ELBOW = 18
V_R_FOREARM = 19
V_R_WRIST = 20

# Left leg: 21-26
V_L_HIP_JOINT = 21
V_L_THIGH = 22
V_L_KNEE = 23
V_L_CALF = 24
V_L_ANKLE = 25

# Right leg: 26-30
V_R_HIP_JOINT = 26
V_R_THIGH = 27
V_R_KNEE = 28
V_R_CALF = 29
V_R_ANKLE = 30

# Region sets for clothing
REGION_SPINE = {V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST,
                V_CHEST, V_NECK}
REGION_L_ARM = {V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID, V_L_BICEP,
                V_L_ELBOW, V_L_FOREARM, V_L_WRIST}
REGION_R_ARM = {V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID, V_R_BICEP,
                V_R_ELBOW, V_R_FOREARM, V_R_WRIST}
REGION_L_LEG = {V_L_HIP_JOINT, V_L_THIGH, V_L_KNEE, V_L_CALF, V_L_ANKLE}
REGION_R_LEG = {V_R_HIP_JOINT, V_R_THIGH, V_R_KNEE, V_R_CALF, V_R_ANKLE}


def build_body_skeleton(cfg):
    """Build the stick-figure skeleton with muscle-definition vertices.

    Returns (verts, edges, radii) where:
        verts: list of (x, y, z) positions
        edges: list of (i, j) index pairs
        radii: dict mapping vertex index to (rx, ry)

    This function is shared between mesh.py and clothing.py so clothing
    can reuse the same skeleton with inflated radii.
    """
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    neck_len = cfg["neck_length"]
    lt = cfg.get("limb_thickness", 1.0)
    td = cfg.get("torso_depth", 0.20)
    gender = cfg.get("gender", "neutral")

    # Vertical layout (bottom-up)
    # Standard 8-head figure: torso divides into ~thirds (hip→navel, navel→chest, chest→shoulder)
    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20     # belly button area
    waist_z = hip_z + torso_len * 0.42            # natural waist (narrowest)
    lower_chest_z = hip_z + torso_len * 0.68      # bottom of ribcage
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len

    # Arm positions
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.04
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    # Muscle vertex positions along arms
    deltoid_z = arm_top_z - upper_arm_len * 0.25
    bicep_z = arm_top_z - upper_arm_len * 0.60
    forearm_z = elbow_z - lower_arm_len * 0.30

    # Muscle vertex positions along legs
    thigh_z = hip_z - (hip_z - knee_z) * 0.35
    calf_z = knee_z - (knee_z - foot_top) * 0.30

    waist_half_w = min(sw, hw) * 0.72

    # --- Gender-specific adjustments ---
    # These modify the radii to create distinct male/female silhouettes.
    # Male: trapezius rise, pectoral protrusion, larger arms/legs, build-scaled
    # Female: hourglass emphasis, wider/rounder glutes, different chest shape
    # Both: enhanced gluteal area compared to neutral

    # Trapezius rise: male inner shoulder is positioned higher
    trap_z_offset = 0.0
    # Pectoral depth multiplier (ry on chest vertices)
    pec_depth = 1.0
    # Neck thickness multiplier
    neck_thick = 1.0
    # Arm muscle multiplier (applied on top of lt)
    arm_muscle = 1.0
    # Leg muscle multiplier
    leg_muscle = 1.0
    # Glute enhancement (pelvis/hip ry multiplier)
    glute_depth = 1.0
    # Hip width radius boost
    hip_rx_mult = 1.0
    # Waist narrowing (lower = narrower)
    waist_mult = 1.0
    # Chest width multiplier
    chest_rx_mult = 1.0

    if gender == "male":
        trap_z_offset = 0.025         # inner shoulder sits higher → trapezius rise
        pec_depth = 1.25              # pectorals protrude forward
        neck_thick = 1.20             # thicker neck
        arm_muscle = 1.25             # much larger arms
        leg_muscle = 1.30             # legs even larger than arms
        glute_depth = 1.15            # enhanced butt area
        chest_rx_mult = 1.08          # wider chest
    elif gender == "female":
        pec_depth = 1.15              # moderate chest protrusion
        neck_thick = 0.88             # slimmer neck
        arm_muscle = 0.88             # slimmer arms
        leg_muscle = 0.95             # slightly slimmer legs
        glute_depth = 1.30            # pronounced butt/hip area
        hip_rx_mult = 1.12            # wider hips
        waist_mult = 0.88             # narrower waist for hourglass
        chest_rx_mult = 0.95          # narrower chest width

    # --- Vertices (31 total) ---
    verts = [
        # Spine (0-6)
        (0, 0, hip_z - 0.02),         # 0: Pelvis base
        (0, 0, hip_z),                 # 1: Hip center
        (0, 0, lower_waist_z),         # 2: Lower waist (belly)
        (0, 0, waist_z),               # 3: Waist (narrowest)
        (0, 0, lower_chest_z),         # 4: Lower chest (rib flare)
        (0, 0, chest_z),               # 5: Chest top
        (0, 0, neck_z),                # 6: Neck top

        # Left arm (7-13) — inner shoulder raised for male trapezius
        (shoulder_x * 0.4, 0, chest_z - 0.01 + trap_z_offset),  # 7: L inner shoulder
        (shoulder_x, 0, arm_top_z),               # 8: L shoulder tip
        (shoulder_x, 0, deltoid_z),               # 9: L deltoid
        (shoulder_x, 0, bicep_z),                 # 10: L bicep peak
        (shoulder_x, 0, elbow_z),                 # 11: L elbow
        (shoulder_x, 0, forearm_z),               # 12: L forearm
        (shoulder_x, 0, wrist_z),                 # 13: L wrist

        # Right arm (14-20) — mirror
        (-shoulder_x * 0.4, 0, chest_z - 0.01 + trap_z_offset),  # 14: R inner shoulder
        (-shoulder_x, 0, arm_top_z),              # 15: R shoulder tip
        (-shoulder_x, 0, deltoid_z),              # 16: R deltoid
        (-shoulder_x, 0, bicep_z),                # 17: R bicep peak
        (-shoulder_x, 0, elbow_z),                # 18: R elbow
        (-shoulder_x, 0, forearm_z),              # 19: R forearm
        (-shoulder_x, 0, wrist_z),                # 20: R wrist

        # Left leg (21-25)
        (hw, 0, hip_z),               # 21: L hip joint
        (hw, 0, thigh_z),             # 22: L thigh peak
        (hw, 0, knee_z),              # 23: L knee
        (hw, 0, calf_z),              # 24: L calf peak
        (hw, 0, foot_top),            # 25: L ankle

        # Right leg (26-30)
        (-hw, 0, hip_z),              # 26: R hip joint
        (-hw, 0, thigh_z),            # 27: R thigh peak
        (-hw, 0, knee_z),             # 28: R knee
        (-hw, 0, calf_z),             # 29: R calf peak
        (-hw, 0, foot_top),           # 30: R ankle

        # Inner hip transitions (31-32) — smooth waist-to-leg curve
        (hw * 0.5, 0, hip_z),         # 31: L inner hip
        (-hw * 0.5, 0, hip_z),        # 32: R inner hip
    ]

    # --- Edges ---
    edges = [
        # Spine
        (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
        # Left arm
        (5, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13),
        # Right arm
        (5, 14), (14, 15), (15, 16), (16, 17), (17, 18), (18, 19), (19, 20),
        # Left leg (via inner hip transition)
        (1, 31), (31, 21), (21, 22), (22, 23), (23, 24), (24, 25),
        # Right leg (via inner hip transition)
        (1, 32), (32, 26), (26, 27), (27, 28), (28, 29), (29, 30),
    ]

    # --- Per-vertex radii (rx, ry) ---
    # Base hourglass silhouette with gender-specific modifications
    radii = {
        # Spine — hourglass with gender shaping
        0:  (hw * hip_rx_mult + 0.04, td * 0.48 * glute_depth),    # Pelvis base
        1:  (hw * hip_rx_mult + 0.05, td * 0.52 * glute_depth),    # Hip center
        2:  (hw * 0.8, td * 0.44),                                  # Lower waist
        3:  (waist_half_w * waist_mult, td * 0.40),                 # Waist (narrowest)
        4:  (sw * 0.90 * chest_rx_mult, td * 0.54 * pec_depth),    # Lower chest
        5:  (sw * 1.05 * chest_rx_mult, td * 0.58 * pec_depth),    # Chest top
        6:  (0.055 * lt * neck_thick, 0.055 * lt * neck_thick),     # Neck

        # Left arm — gender-scaled muscle
        7:  (sw * 0.40, td * 0.45 * arm_muscle),            # L inner shoulder
        8:  (0.068 * lt * arm_muscle, 0.060 * lt * arm_muscle),  # L shoulder tip
        9:  (0.072 * lt * arm_muscle, 0.064 * lt * arm_muscle),  # L deltoid
        10: (0.062 * lt * arm_muscle, 0.058 * lt * arm_muscle),  # L bicep peak
        11: (0.046 * lt * arm_muscle, 0.046 * lt * arm_muscle),  # L elbow
        12: (0.052 * lt * arm_muscle, 0.048 * lt * arm_muscle),  # L forearm
        13: (0.038 * lt * arm_muscle, 0.034 * lt * arm_muscle),  # L wrist

        # Right arm — mirror
        14: (sw * 0.40, td * 0.45 * arm_muscle),            # R inner shoulder
        15: (0.068 * lt * arm_muscle, 0.060 * lt * arm_muscle),  # R shoulder tip
        16: (0.072 * lt * arm_muscle, 0.064 * lt * arm_muscle),  # R deltoid
        17: (0.062 * lt * arm_muscle, 0.058 * lt * arm_muscle),  # R bicep peak
        18: (0.046 * lt * arm_muscle, 0.046 * lt * arm_muscle),  # R elbow
        19: (0.052 * lt * arm_muscle, 0.048 * lt * arm_muscle),  # R forearm
        20: (0.038 * lt * arm_muscle, 0.034 * lt * arm_muscle),  # R wrist

        # Left leg — gender-scaled muscle (thicker for realistic proportions)
        21: (0.105 * lt * leg_muscle, 0.095 * lt * leg_muscle * glute_depth),   # L hip joint
        22: (0.112 * lt * leg_muscle, 0.098 * lt * leg_muscle),  # L thigh peak
        23: (0.074 * lt * leg_muscle, 0.072 * lt * leg_muscle),  # L knee
        24: (0.082 * lt * leg_muscle, 0.074 * lt * leg_muscle),  # L calf peak
        25: (0.058 * lt * leg_muscle, 0.056 * lt * leg_muscle),  # L ankle

        # Right leg — mirror
        26: (0.105 * lt * leg_muscle, 0.095 * lt * leg_muscle * glute_depth),   # R hip joint
        27: (0.112 * lt * leg_muscle, 0.098 * lt * leg_muscle),  # R thigh peak
        28: (0.074 * lt * leg_muscle, 0.072 * lt * leg_muscle),  # R knee
        29: (0.082 * lt * leg_muscle, 0.074 * lt * leg_muscle),  # R calf peak
        30: (0.058 * lt * leg_muscle, 0.056 * lt * leg_muscle),  # R ankle

        # Inner hip transitions — blend between spine and hip joint radii
        31: (hw * hip_rx_mult * 0.6, td * 0.50 * glute_depth),   # L inner hip
        32: (hw * hip_rx_mult * 0.6, td * 0.50 * glute_depth),   # R inner hip
    }

    return verts, edges, radii


def _apply_skin_modifier(verts, edges, radii, name="SkinBody",
                         branch_smoothing=0.7, subsurf_level=1,
                         use_mirror=True):
    """Create a mesh from skeleton and apply Skin + Subdivision Surface.

    Args:
        verts, edges, radii: from build_body_skeleton()
        name: object name
        branch_smoothing: 0-1, how smooth branch junctions are
        subsurf_level: subdivision level (0 = no subdivision)
        use_mirror: if True, delete the X<0 half after Skin/Subsurf and
            apply a Mirror modifier to guarantee perfect left-right symmetry.

    Returns the mesh object with modifiers applied.
    """
    import bmesh

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Skin modifier
    skin_mod = obj.modifiers.new(name="Skin", type='SKIN')
    skin_mod.branch_smoothing = branch_smoothing
    skin_mod.use_smooth_shade = True

    # Set per-vertex radii and mark root
    skin_data = mesh.skin_vertices[0].data
    for i, sv in enumerate(skin_data):
        rx, ry = radii.get(i, (0.05, 0.05))
        sv.radius = (rx, ry)
        if i == 0:
            sv.use_root = True

    # Subdivision Surface
    if subsurf_level > 0:
        subsurf = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        subsurf.levels = subsurf_level
        subsurf.render_levels = subsurf_level

    # Apply modifiers
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Skin")
    if subsurf_level > 0:
        bpy.ops.object.modifier_apply(modifier="Subsurf")

    # Laplacian Smooth to soften sharp edges while preserving body shape
    lap_smooth = obj.modifiers.new(name="LaplacianSmooth", type='LAPLACIANSMOOTH')
    lap_smooth.lambda_factor = 0.3
    lap_smooth.iterations = 3
    lap_smooth.use_volume_preserve = True
    bpy.ops.object.modifier_apply(modifier="LaplacianSmooth")

    # Enforce perfect symmetry via Mirror modifier
    if use_mirror:
        # Cleanly bisect the mesh at X=0 and remove the negative X side
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        # Bisect at the YZ plane (X=0), clearing geometry on the negative side
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(
            bm, geom=geom,
            plane_co=(0, 0, 0),
            plane_no=(1, 0, 0),  # X-axis normal
            clear_inner=True,     # remove X < 0 side
            clear_outer=False,
        )

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        # Add and apply Mirror modifier on X axis
        mirror = obj.modifiers.new(name="Mirror", type='MIRROR')
        mirror.use_axis[0] = True       # Mirror on X
        mirror.use_axis[1] = False
        mirror.use_axis[2] = False
        mirror.use_mirror_merge = True
        mirror.merge_threshold = 0.002
        mirror.use_clip = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier="Mirror")

    return obj


def _create_foot(name, foot_w, foot_len, location, side="L"):
    """Create a low-poly tapered foot/shoe shape.

    Builds a wedge-shaped foot with a wider heel tapering to a narrower
    toe section. The foot points along -Y (forward in Blender/glTF).
    ~20 faces per foot — much more readable than a plain box.

    Args:
        name: object name (e.g. "Foot.L")
        foot_w: foot width
        foot_len: foot length (heel to toe)
        location: (x, y, z) ankle attachment point
        side: "L" or "R"
    """
    import bmesh

    bm = bmesh.new()
    x0, y0, z0 = location

    # Foot dimensions
    hw = foot_w / 2          # half width
    h = 0.06                 # foot height
    toe_taper = 0.65         # toe narrows to 65% of heel width
    toe_h = h * 0.7          # toe section is slightly thinner

    # Heel is at y0, toe extends forward (-Y)
    heel_y = y0 + foot_len * 0.3     # heel back
    mid_y = y0 - foot_len * 0.2      # ball of foot
    toe_y = y0 - foot_len * 0.7      # toe tip

    # Vertices — 12 verts forming 3 cross-sections (heel, mid, toe)
    # Bottom face (Z = 0, ground level)
    v0 = bm.verts.new((x0 - hw,              heel_y,  0))          # heel back-inner
    v1 = bm.verts.new((x0 + hw,              heel_y,  0))          # heel back-outer
    v2 = bm.verts.new((x0 + hw,              mid_y,   0))          # mid-outer
    v3 = bm.verts.new((x0 - hw,              mid_y,   0))          # mid-inner
    v4 = bm.verts.new((x0 + hw * toe_taper,  toe_y,   0))          # toe-outer
    v5 = bm.verts.new((x0 - hw * toe_taper,  toe_y,   0))          # toe-inner

    # Top face (ankle height)
    v6 = bm.verts.new((x0 - hw * 0.85,       heel_y,  h))          # heel top back-inner
    v7 = bm.verts.new((x0 + hw * 0.85,       heel_y,  h))          # heel top back-outer
    v8 = bm.verts.new((x0 + hw * 0.85,       mid_y,   h))          # mid top-outer
    v9 = bm.verts.new((x0 - hw * 0.85,       mid_y,   h))          # mid top-inner
    v10 = bm.verts.new((x0 + hw * toe_taper * 0.8, toe_y, toe_h))  # toe top-outer
    v11 = bm.verts.new((x0 - hw * toe_taper * 0.8, toe_y, toe_h))  # toe top-inner

    # Faces — heel section (4 sides + bottom + top)
    bm.faces.new([v0, v1, v2, v3])      # bottom heel
    bm.faces.new([v6, v9, v8, v7])      # top heel
    bm.faces.new([v0, v6, v7, v1])      # back
    bm.faces.new([v1, v7, v8, v2])      # outer heel
    bm.faces.new([v0, v3, v9, v6])      # inner heel

    # Faces — toe section (4 sides + bottom + top)
    bm.faces.new([v3, v2, v4, v5])      # bottom toe
    bm.faces.new([v9, v11, v10, v8])    # top toe
    bm.faces.new([v2, v8, v10, v4])     # outer toe
    bm.faces.new([v3, v5, v11, v9])     # inner toe
    bm.faces.new([v4, v10, v11, v5])    # toe tip

    # Build mesh
    mesh_data = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh_data)
    bm.free()

    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    return obj


def _create_shaped_head(name, head_r, location, segments=10, rings=7):
    """Create a smooth, round head sphere with subtle facial deformation.

    Builds a UV sphere, applies gentle vertex displacement for jaw/brow/cheeks,
    then applies a Subdivision Surface modifier (level 1) + smooth shading
    to produce a smooth, round result before joining with the body.

    In Blender, -Y is the forward/face direction (maps to -Z in glTF).
    """
    import bmesh

    # Create base sphere
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings,
        radius=head_r, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name

    # Apply gentle elliptical scaling — keep it mostly round
    obj.scale = (0.94, 0.96, 1.02)
    bpy.ops.object.transform_apply(scale=True)

    # Deform vertices for facial features using bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    cx, cy, cz = location
    # Effective radii after scaling
    rx_eff = head_r * 0.94
    rz_eff = head_r * 1.02

    for v in bm.verts:
        # Position relative to head center
        rel_x = v.co.x - cx
        rel_y = v.co.y - cy
        rel_z = v.co.z - cz

        # Normalized height: 0 at bottom, 1 at top
        norm_z = (rel_z + rz_eff) / (2.0 * rz_eff)
        norm_z = max(0.0, min(1.0, norm_z))

        # Front-facing factor: 1 at front (negative Y in Blender), 0 at back
        front = max(0.0, -rel_y) / (head_r * 0.96) if head_r > 0 else 0
        front = min(1.0, front)

        # --- Gentle jaw narrowing (lower 25% of head) ---
        if norm_z < 0.25:
            t = (0.25 - norm_z) / 0.25
            v.co.x -= rel_x * 0.10 * t  # very subtle narrowing

        # --- Subtle brow ridge (57-63% height, front-facing only) ---
        if 0.57 < norm_z < 0.63 and front > 0.4:
            brow_t = 1.0 - abs(norm_z - 0.60) / 0.03
            brow_t = max(0.0, brow_t)
            v.co.y -= head_r * 0.008 * brow_t * front

        # --- Very gentle cheekbone push (42-52% height) ---
        side_factor = abs(rel_x) / rx_eff if rx_eff > 0 else 0
        side_factor = min(1.0, side_factor)
        if 0.42 < norm_z < 0.52 and side_factor > 0.4 and front > 0.2:
            cheek_t = 1.0 - abs(norm_z - 0.47) / 0.05
            cheek_t = max(0.0, min(1.0, cheek_t))
            push = head_r * 0.008 * cheek_t * side_factor
            if rel_x > 0:
                v.co.x += push
            else:
                v.co.x -= push

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    # Apply Subdivision Surface modifier for smoothness (level 1)
    bpy.context.view_layer.objects.active = obj
    subsurf = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    subsurf.levels = 1
    subsurf.render_levels = 1
    bpy.ops.object.modifier_apply(modifier="Subsurf")

    # Apply smooth shading to the head
    bpy.ops.object.shade_smooth()

    return obj


def create_body(cfg):
    """Build the complete humanoid mesh from config values.

    The character is built standing upright with feet at Z=0.
    Uses Blender's Skin modifier for the torso, arms, and legs to create
    smooth organic forms with natural shoulder rounding and muscle definition.
    Head, hands, feet, and facial features are added as separate primitives.

    Args:
        cfg: dict with body proportion values.

    Returns:
        Tuple of (body_obj, hair_obj_or_None, clothing_list).
    """
    _clear_scene()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    head_r = cfg["head_size"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    neck_len = cfg["neck_length"]
    hand_size = cfg["hand_size"]
    foot_len = cfg["foot_length"]
    foot_w = cfg["foot_width"]
    lt = cfg.get("limb_thickness", 1.0)
    td = cfg.get("torso_depth", 0.20)
    skin_tone = cfg.get("skin_tone", None)

    # Vertical layout
    foot_top = 0.06
    hip_z = foot_top + leg_len
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len
    head_z = neck_z + head_r

    # Arm positions
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.04
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    parts = []

    # --- Skin-modifier body (torso + arms + legs) ---
    verts, edges, radii = build_body_skeleton(cfg)
    skin_body = _apply_skin_modifier(verts, edges, radii, name="SkinBody",
                                     branch_smoothing=1.0, subsurf_level=2)
    parts.append(skin_body)

    # --- Head (shaped sphere with facial deformation) ---
    head = _create_shaped_head("Head", head_r, (0, 0, head_z))
    parts.append(head)

    # --- Hands (low-poly mitt with thumb) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        hand = _create_hand(
            f"Hand.{side}", hand_size,
            (x_sign * shoulder_x, 0, wrist_z),
            side=side,
        )
        parts.append(hand)

    # --- Feet (tapered wedge shape) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw
        foot = _create_foot(
            f"Foot.{side}", foot_w, foot_len,
            (x, 0, foot_top), side=side,
        )
        parts.append(foot)

    # --- Face (eyes + nose) ---
    # Note: In Blender, -Y is the forward direction (toward camera in glTF).
    eye_r = head_r * 0.06
    eye_spacing = head_r * 0.28
    eye_y = -(head_r * 0.82)
    eye_z = head_z + head_r * 0.12

    eye_mat = bpy.data.materials.new(name="Eye_Material")
    eye_mat.use_nodes = True
    eye_bsdf = eye_mat.node_tree.nodes.get("Principled BSDF")
    if eye_bsdf:
        eye_bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.08, 1.0)
        eye_bsdf.inputs["Roughness"].default_value = 0.3

    for side, x_sign in [("L", 1), ("R", -1)]:
        eye = _create_sphere(
            f"Eye.{side}", eye_r,
            (x_sign * eye_spacing, eye_y, eye_z),
            segments=6, rings=4,
        )
        eye.data.materials.append(eye_mat)
        parts.append(eye)

    nose_r = head_r * 0.07
    nose = _create_sphere(
        "Nose", nose_r,
        (0, -(head_r * 0.86), head_z - head_r * 0.06),
        segments=6, rings=4,
    )
    parts.append(nose)

    # --- Join all parts ---
    body = _join_objects(parts)

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    # Smooth shading
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.shade_smooth()
    mod = body.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(50)

    _apply_material(body, skin_tone)

    # --- Hair (separate object, will be parented to Head bone) ---
    hair_obj = None
    hair_style = cfg.get("hair_style", "short")
    hair_color = cfg.get("hair_color", None)
    if hair_style and hair_style != "none":
        from . import hair as hair_module
        hair_obj = hair_module.create_hair(head_z, head_r, hair_style, hair_color)

    # --- Clothing (separate objects, skinned to armature) ---
    clothing_objs = []
    clothing_type = cfg.get("clothing", "tshirt,pants")
    if clothing_type and clothing_type != "none":
        from . import clothing as clothing_module
        clothing_color = cfg.get("clothing_color", None)
        clothing_objs = clothing_module.create_clothing(cfg, clothing_type,
                                                        clothing_color)

    return body, hair_obj, clothing_objs
