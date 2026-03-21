"""Demon bartender mesh additions — horns, tail, and other demon features.

Each function takes an existing armature object and a config dict, then
attaches the new mesh as a child parented to the appropriate bone.

Conventions:
    - All meshes are positioned in world space then re-parented with bone
      parenting so they follow the skeleton correctly.
    - Materials use Principled BSDF with explicit dark reddish-black colors
      matching the demon skin tone aesthetic.
    - Horn and tail geometry uses Blender primitives for low-poly compatibility
      (target: 300-500 total faces per asset).
"""

import math


# ---------------------------------------------------------------------------
# Shared material helper
# ---------------------------------------------------------------------------

def _make_demon_material(name, base_color=(0.08, 0.01, 0.01, 1.0), roughness=0.6, metallic=0.0):
    """Create and return a Principled BSDF material with the given properties."""
    import bpy
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


# ---------------------------------------------------------------------------
# Horns
# ---------------------------------------------------------------------------

def add_horns(armature, cfg):
    """Add two curved demon horns parented to the Head bone.

    Each horn is a tapered cone (6-sided) leaning outward and slightly
    backward from the top of the head. The mesh is kept low-poly by using
    Blender's primitive cone operator with a small vertex count.

    Args:
        armature: The Blender armature object.
        cfg: Config dict with keys 'horn_height' and 'horn_curve'.
    """
    import bpy
    import mathutils

    h = cfg.get("horn_height", 0.18)
    curve = cfg.get("horn_curve", 0.08)

    # Determine head bone tip position in world space for vertical placement
    head_bone = armature.pose.bones.get("Head")
    head_z = 0.0
    if head_bone:
        head_world_tail = armature.matrix_world @ head_bone.tail
        head_z = head_world_tail.z

    # Outward lean angle derived from the curve parameter:
    # More curve → steeper outward lean.  Clamped to a reasonable range.
    lean_deg = min(35.0, max(5.0, curve * 200.0))

    for side, label in [(1, "L"), (-1, "R")]:
        # Deselect everything so context.active_object is reliable
        bpy.ops.object.select_all(action='DESELECT')

        # Create a 6-sided tapered cone along local Z
        bpy.ops.mesh.primitive_cone_add(
            vertices=6,
            radius1=0.025,   # base radius: 2.5 cm
            radius2=0.001,   # tip radius: ~1 mm (near-point)
            depth=h,
            location=(0.0, 0.0, 0.0),
        )
        horn = bpy.context.active_object
        horn.name = f"DemonHorn_{label}"

        # Apply demon horn material
        mat = _make_demon_material(
            name=f"HornMat_{label}",
            base_color=(0.08, 0.01, 0.01, 1.0),
            roughness=0.6,
            metallic=0.0,
        )
        horn.data.materials.clear()
        horn.data.materials.append(mat)

        # Position: place at side of head, just below the very top
        #   X: outward by ~9 cm (plus curve contribution)
        #   Y: lean back slightly
        #   Z: at head_z minus a small offset so base sits at head top
        horn.location.x = side * (0.09 + curve * 0.5)
        horn.location.y = -0.03
        horn.location.z = head_z - 0.02

        # Lean the horn outward (rotation around Y axis) and slightly forward
        horn.rotation_euler.y = side * math.radians(lean_deg)
        horn.rotation_euler.x = math.radians(-5)   # slight backward tilt

        # Parent to armature with bone parenting so horn follows the Head bone
        horn.parent = armature
        horn.parent_type = 'BONE'
        horn.parent_bone = "Head"

        # Correct the parent inverse so the horn stays at its current world
        # position after reparenting (Blender does not do this automatically
        # when setting parent_type programmatically).
        horn.matrix_parent_inverse = (
            armature.matrix_world @ armature.data.bones["Head"].matrix_local
        ).inverted() if "Head" in armature.data.bones else armature.matrix_world.inverted()


# ---------------------------------------------------------------------------
# Tail
# ---------------------------------------------------------------------------

def add_tail(armature, cfg):
    """Add a segmented demon tail parented to the Hips bone.

    The tail is built from a series of cylinders, each slightly smaller
    in radius and rotated to create a sweeping upward-then-drooping curve.
    Segments are joined into a single mesh for efficiency.

    Args:
        armature: The Blender armature object.
        cfg: Config dict with key 'tail_length'.
    """
    import bpy
    import mathutils

    tail_length = cfg.get("tail_length", 0.55)

    # Locate hips bone in world space
    hips_bone = armature.pose.bones.get("Hips")
    hips_world_pos = mathutils.Vector((0.0, 0.0, 0.0))
    if hips_bone:
        hips_world_pos = armature.matrix_world @ hips_bone.head

    # Tail parameters: 5 segments
    num_segments = 5
    seg_length = tail_length / num_segments

    # Each segment: (radius, cumulative_x_offset, cumulative_z_offset, x_rotation_deg)
    # The tail starts at the base of the spine (behind hips), curves up and
    # then droops down at the tip — a classic demon tail silhouette.
    segment_params = [
        # (radius, local_y_step, local_z_step, rotation_x_deg)
        (0.030, -0.05, 0.00,  10),   # base: emerges backward and slightly up
        (0.025, -0.05, 0.04,  30),   # curves upward
        (0.018, -0.03, 0.06,  20),   # continues up
        (0.012, -0.02, 0.04, -10),   # begins to droop
        (0.006, -0.02, -0.02, -30),  # tip droops downward
    ]

    segment_objects = []
    accumulated_loc = mathutils.Vector((
        0.0,
        hips_world_pos.y - 0.06,   # start behind the hips
        hips_world_pos.z - 0.04,   # slightly below hips center
    ))
    accumulated_rot_x = 0.0

    for i, (radius, dy, dz, rot_x) in enumerate(segment_params):
        bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6,
            radius=radius,
            depth=seg_length,
            location=(
                accumulated_loc.x,
                accumulated_loc.y + dy * i,
                accumulated_loc.z + dz * i,
            ),
        )
        seg = bpy.context.active_object
        seg.name = f"DemonTail_seg{i}"

        # Rotate to follow the tail curve: tip each segment along its local X
        accumulated_rot_x += rot_x
        seg.rotation_euler.x = math.radians(accumulated_rot_x)

        # Apply demon material
        mat = _make_demon_material(
            name=f"TailMat_{i}",
            base_color=(0.08, 0.01, 0.01, 1.0),
            roughness=0.65,
            metallic=0.0,
        )
        seg.data.materials.clear()
        seg.data.materials.append(mat)

        segment_objects.append(seg)

    # Join all segments into one tail mesh object
    if segment_objects:
        bpy.ops.object.select_all(action='DESELECT')
        for seg in segment_objects:
            seg.select_set(True)
        bpy.context.view_layer.objects.active = segment_objects[0]
        if len(segment_objects) > 1:
            bpy.ops.object.join()
        tail = bpy.context.active_object
        tail.name = "DemonTail"

        # Parent tail to armature at the Hips bone
        tail.parent = armature
        tail.parent_type = 'BONE'
        tail.parent_bone = "Hips"

        tail.matrix_parent_inverse = (
            armature.matrix_world @ armature.data.bones["Hips"].matrix_local
        ).inverted() if "Hips" in armature.data.bones else armature.matrix_world.inverted()

        return tail

    return None
