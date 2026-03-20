"""Low-poly eye generation for the humanoid pipeline.

Each eye is a single small black sphere (~32 faces).

Public interface
----------------
  create_eyes(head_z, head_r, eye_color, face_y)  →  [eyes_obj]
  create_eyebrows(head_z, head_r, face_y, brow_color)  →  brow_obj
  EYE_COLORS  — dict mapping name → RGBA tuple (kept for API compatibility)
"""

import math

EYE_COLORS = {
    "brown":      (0.15, 0.08, 0.04, 1.0),
    "dark_brown": (0.10, 0.05, 0.02, 1.0),
    "blue":       (0.20, 0.35, 0.65, 1.0),
    "green":      (0.12, 0.42, 0.18, 1.0),
    "grey":       (0.40, 0.40, 0.42, 1.0),
    "hazel":      (0.28, 0.22, 0.08, 1.0),
}

# ── Shared geometry constants ─────────────────────────────────────────────────
# All functions that need eye/brow positions import these helpers so values
# stay in sync automatically.

def _eye_geometry(head_z, head_r, face_y):
    """Return (eye_r, eye_x, eye_z, eye_y, disc_y) for the current head."""
    eye_r  = head_r * 0.09
    eye_z  = head_z - head_r * 0.1
    eye_x  = head_r * 0.32
    if face_y is not None:
        disc_y = face_y + head_r * 0.65
        eye_y  = disc_y + eye_r
    else:
        eye_y  = -(head_r * 0.85)
        disc_y = eye_y - eye_r * 0.88
    return eye_r, eye_x, eye_z, eye_y, disc_y


def create_eyes(head_z, head_r, eye_color=None, face_y=None):
    """Build two small black eye spheres, returning a single mesh object.

    Args:
        head_z:     Z of the head centre.
        head_r:     Head radius in metres.
        eye_color:  Ignored (kept for API compatibility).
        face_y:     Most-forward Y of the body mesh (nose-tip bounding-box Y).

    Returns:
        [eyes_obj]  — one bpy.types.Object containing both spheres.
    """
    import bpy
    import bmesh as bmesh_mod
    import mathutils

    eye_r, eye_x, eye_z, eye_y, _ = _eye_geometry(head_z, head_r, face_y)

    bm = bmesh_mod.new()
    for x_sign in (1, -1):
        bmesh_mod.ops.create_uvsphere(
            bm,
            u_segments=8,
            v_segments=4,
            radius=eye_r,
            matrix=mathutils.Matrix.Translation((x_sign * eye_x, eye_y, eye_z)),
            calc_uvs=False,
        )
    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_s = bpy.data.meshes.new("Eyeballs_Mesh")
    bm.to_mesh(mesh_s)
    mesh_s.update()
    bm.free()

    eyes_obj = bpy.data.objects.new("Eyeballs", mesh_s)
    bpy.context.collection.objects.link(eyes_obj)
    bpy.context.view_layer.objects.active = eyes_obj
    eyes_obj.select_set(True)
    bpy.ops.object.shade_smooth()

    eye_mat = bpy.data.materials.new("Eye_Black")
    eye_mat.use_nodes = True
    bsdf = eye_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.10
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.8
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.8
    eyes_obj.data.materials.append(eye_mat)

    return [eyes_obj]


def create_eyebrows(head_z, head_r, face_y=None, brow_color=None):
    """Build low-poly eyebrow strips sitting just above the eye spheres.

    Args:
        head_z:     Z of the head centre.
        head_r:     Head radius in metres.
        face_y:     Most-forward Y of the body mesh (nose-tip bounding-box Y).
        brow_color: RGBA tuple or None (defaults to dark brown).

    Returns:
        brow_obj — one bpy.types.Object containing both brow strips.
    """
    import bpy
    import bmesh as bmesh_mod

    if brow_color is None:
        brow_rgba = (0.09, 0.05, 0.02, 1.0)
    else:
        brow_rgba = tuple(brow_color)

    eye_r, eye_x, eye_z, _, disc_y = _eye_geometry(head_z, head_r, face_y)

    # Brow sits immediately above the top of the eye sphere
    brow_z     = eye_z + eye_r + head_r * 0.015   # bottom edge of brow
    brow_h     = head_r * 0.028                    # strip height (Z)
    brow_half_w = head_r * 0.18                    # half-width of each brow
    brow_y     = disc_y                            # same depth as eye surface
    n_segs     = 5

    bm = bmesh_mod.new()

    for x_sign in (1, -1):
        cx = x_sign * eye_x
        bot_verts = []
        top_verts = []
        for i in range(n_segs + 1):
            t = i / n_segs   # 0 = inner (nose side), 1 = outer
            x = cx + x_sign * (-brow_half_w + 2.0 * brow_half_w * t)
            # subtle arch peaking near t=0.4; tapers thinner toward outer end
            arch_z  = brow_z + brow_h * 4.0 * t * (1.0 - t) * 0.30
            taper_h = brow_h * (1.0 - 0.40 * t)
            bot_verts.append(bm.verts.new((x, brow_y, arch_z)))
            top_verts.append(bm.verts.new((x, brow_y, arch_z + taper_h)))

        for i in range(n_segs):
            try:
                if x_sign > 0:
                    bm.faces.new([bot_verts[i], bot_verts[i + 1],
                                  top_verts[i + 1], top_verts[i]])
                else:
                    bm.faces.new([bot_verts[i + 1], bot_verts[i],
                                  top_verts[i], top_verts[i + 1]])
            except ValueError:
                pass

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_b = bpy.data.meshes.new("Eyebrows_Mesh")
    bm.to_mesh(mesh_b)
    mesh_b.update()
    bm.free()

    brow_obj = bpy.data.objects.new("Eyebrows", mesh_b)
    bpy.context.collection.objects.link(brow_obj)

    brow_mat = bpy.data.materials.new("Eyebrow_Mat")
    brow_mat.use_nodes = True
    bsdf = brow_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = brow_rgba
        bsdf.inputs["Roughness"].default_value = 0.85
    brow_obj.data.materials.append(brow_mat)

    return brow_obj
