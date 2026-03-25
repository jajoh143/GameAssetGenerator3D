"""Low-poly flat-disc eye generation for the humanoid pipeline.

Each eye is a single flat black oval — a simple triangle fan.  No
sclera/iris/pupil zones; just one opaque black disc per eye.

Both eyes share one mesh object (Eyes_Disc) with a single material slot.
Total eye geometry: ~16 faces (both eyes, 8 triangles × 2 eyes).

Public interface
----------------
  create_eyes(head_z, head_r, eye_color, face_y)  →  [eye_disc_obj]
  create_eyebrows(head_z, head_r, face_y, brow_color)  →  brow_obj
"""

import math

# ── Shared geometry constants ─────────────────────────────────────────────────

# Eyes sit at or very slightly in front of the face surface (disc_y = face_y).
# face_y is sampled from actual head vertices at eye level, so it is the
# true face-surface depth at the eye socket.  A small forward nudge (negative
# fraction of head_r_horiz) lets the cartoon disc "pop" just off the surface.
_EYE_FORWARD = 0.02   # disc protrudes 2 % of horizontal head radius forward


def _eye_geometry(head_z, head_r, face_y, head_r_horiz=None):
    """Return (eye_r, eye_x, eye_z, eye_y, disc_y) for the current head.

    Args:
        head_r:       Vertical head radius — used for Z offsets only.
        head_r_horiz: Horizontal head half-width — used for eye_r and eye_x
                      sizing so eyes scale with the actual head width.
                      Falls back to head_r when None.
        face_y:       Most-forward Y of the face at eye level (from vertex
                      sampling in template_mesh).  Eyes are placed at this
                      Y, with a small forward nudge so they sit on the surface.
    """
    hr_h   = head_r_horiz if head_r_horiz is not None else head_r
    eye_r  = hr_h * 0.085          # scales with horizontal head width
    eye_z  = head_z - head_r * 0.05  # just below equator (vertical offset)
    eye_x  = hr_h * 0.28           # lateral separation scales with head width

    if face_y is not None:
        # Place disc slightly forward of (in front of) the face surface
        disc_y = face_y - hr_h * _EYE_FORWARD
    else:
        # Fallback: spherical approximation (NBM-era behaviour)
        disc_y = -(hr_h * 0.62)

    eye_y = disc_y - eye_r
    return eye_r, eye_x, eye_z, eye_y, disc_y


def create_eyes(head_z, head_r, eye_color=None, face_y=None, head_r_horiz=None):
    """Build flat low-poly black oval eyes for left and right eyes.

    Each eye is a single flat elliptical disc — a triangle fan from the
    centre vertex to an 8-segment oval ring.  One black matte material,
    no zones.

    Args:
        head_z:       Z of the head equator.
        head_r:       Vertical head radius in metres.
        head_r_horiz: Horizontal head half-width — used for eye sizing.
        eye_color:    Ignored (kept for API compatibility).
        face_y:       Face-surface Y at eye level (from vertex sampling).

    Returns:
        [eye_disc_obj]  — one bpy.types.Object containing both eyes (~16 faces).
    """
    import bpy
    import bmesh as bmesh_mod

    eye_r, eye_x, eye_z, _eye_y, disc_y = _eye_geometry(head_z, head_r, face_y, head_r_horiz)

    # Oval proportions — wider than tall
    rx = eye_r * 1.40
    ry = eye_r * 0.90
    n  = 8

    bm = bmesh_mod.new()

    for x_sign in (1, -1):
        cx = x_sign * eye_x
        y  = disc_y

        center_v = bm.verts.new((cx, y, eye_z))
        ring_vs  = [
            bm.verts.new((
                cx + rx * math.cos(2 * math.pi * i / n),
                y,
                eye_z + ry * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]

        for i in range(n):
            j = (i + 1) % n
            try:
                if x_sign > 0:
                    bm.faces.new([center_v, ring_vs[i], ring_vs[j]])
                else:
                    bm.faces.new([center_v, ring_vs[j], ring_vs[i]])
            except ValueError:
                pass

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    eye_mesh = bpy.data.meshes.new("Eye_Disc_Mesh")
    bm.to_mesh(eye_mesh)
    eye_mesh.update()
    bm.free()

    eye_obj = bpy.data.objects.new("Eyes_Disc", eye_mesh)
    bpy.context.collection.objects.link(eye_obj)

    mat = bpy.data.materials.new("Eye_Black")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.10
    eye_obj.data.materials.append(mat)

    return [eye_obj]


def create_eyebrows(head_z, head_r, face_y=None, brow_color=None, head_r_horiz=None):
    """Build low-poly eyebrow strips sitting just above the eye sockets.

    Args:
        head_z:       Z of the head equator.
        head_r:       Vertical head radius in metres.
        head_r_horiz: Horizontal head half-width — used for brow sizing.
        face_y:       Face-surface Y at eye level (from vertex sampling).
        brow_color:   RGBA tuple or None (defaults to dark brown).

    Returns:
        brow_obj — one bpy.types.Object containing both brow strips.
    """
    import bpy
    import bmesh as bmesh_mod

    if brow_color is None:
        brow_rgba = (0.09, 0.05, 0.02, 1.0)
    else:
        brow_rgba = tuple(brow_color)

    eye_r, eye_x, eye_z, _, disc_y = _eye_geometry(head_z, head_r, face_y, head_r_horiz)

    hr_h        = head_r_horiz if head_r_horiz is not None else head_r
    brow_z      = eye_z + eye_r + head_r * 0.015
    brow_h      = hr_h * 0.028
    brow_half_w = hr_h * 0.18
    brow_y      = disc_y
    n_segs      = 5

    bm = bmesh_mod.new()

    for x_sign in (1, -1):
        cx = x_sign * eye_x
        bot_verts = []
        top_verts = []
        for i in range(n_segs + 1):
            t = i / n_segs
            x = cx + x_sign * (-brow_half_w + 2.0 * brow_half_w * t)
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
