"""Low-poly flat-disc eye generation for the humanoid pipeline.

Each eye is a single flat elliptical disc with three concentric material zones:
  • Outer zone  – sclera / white of the eye
  • Middle zone – iris (coloured)
  • Centre zone – pupil (near-black, glossy)

Both eyes share one mesh object (Eyes_Disc) with three material slots.
Total eye geometry: ~48 faces (both eyes, 8 segments × 3 zones × 2 eyes).

Public interface
----------------
  create_eyes(head_z, head_r, eye_color, face_y)  →  [eye_disc_obj]
  create_eyebrows(head_z, head_r, face_y, brow_color)  →  brow_obj
"""

import math

# ── Shared geometry constants ─────────────────────────────────────────────────

def _eye_geometry(head_z, head_r, face_y):
    """Return (eye_r, eye_x, eye_z, eye_y, disc_y) for the current head."""
    eye_r  = head_r * 0.09
    eye_z  = head_z - head_r * 0.1
    eye_x  = head_r * 0.32
    # Position the disc at the eye socket inner ring depth from base_mesh.py:
    # face surface at Y = -0.86 * head_r, socket recess = 0.04 * head_r,
    # so disc sits at Y = -0.82 * head_r (in world coords, body centred at Y=0).
    disc_y = -(head_r * 0.82)
    eye_y  = disc_y - eye_r
    return eye_r, eye_x, eye_z, eye_y, disc_y


def _set_specular(bsdf, value):
    """Set specular on Principled BSDF, handling API differences across Blender versions."""
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = value
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = value


def _default_iris_color(eye_color):
    """Return an RGBA tuple for the iris, defaulting to warm brown."""
    if eye_color is None:
        return (0.35, 0.18, 0.05, 1.0)
    c = tuple(eye_color)
    return c if len(c) == 4 else (*c, 1.0)


def create_eyes(head_z, head_r, eye_color=None, face_y=None):
    """Build flat low-poly eye discs for left and right eyes.

    Each eye is a single elliptical disc with three concentric zones:
      slot 0 – pupil  (near-black, glossy centre)
      slot 1 – iris   (coloured mid-ring)
      slot 2 – sclera (off-white outer ring)

    The disc is wider than tall to match a natural eye shape, and sits flat
    at socket depth so it reads as part of the face rather than a protruding
    sphere.

    Args:
        head_z:    Z of the head centre.
        head_r:    Head radius in metres.
        eye_color: RGBA or RGB tuple for iris colour, or None (warm brown).
        face_y:    Most-forward Y of the body mesh (nose-tip bounding-box Y).

    Returns:
        [eye_disc_obj]  — one bpy.types.Object containing both eyes (~48 faces).
    """
    import bpy
    import bmesh as bmesh_mod

    eye_r, eye_x, eye_z, _eye_y, disc_y = _eye_geometry(head_z, head_r, face_y)
    iris_rgba = _default_iris_color(eye_color)

    # Elliptical proportions — eyes are wider than tall
    sclera_rx = eye_r * 1.40   # horizontal radius (white outer)
    sclera_ry = eye_r * 0.90   # vertical radius
    iris_rx   = sclera_rx * 0.62
    iris_ry   = sclera_ry * 0.62
    pupil_rx  = iris_rx * 0.46
    pupil_ry  = iris_ry * 0.46

    n = 8   # segments per zone — low poly, matches reference style

    bm = bmesh_mod.new()

    for x_sign in (1, -1):
        cx = x_sign * eye_x
        y  = disc_y  # flat at socket depth

        center_v = bm.verts.new((cx, y, eye_z))

        pupil_vs = [
            bm.verts.new((
                cx + pupil_rx * math.cos(2 * math.pi * i / n),
                y,
                eye_z + pupil_ry * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]
        iris_vs = [
            bm.verts.new((
                cx + iris_rx * math.cos(2 * math.pi * i / n),
                y,
                eye_z + iris_ry * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]
        sclera_vs = [
            bm.verts.new((
                cx + sclera_rx * math.cos(2 * math.pi * i / n),
                y,
                eye_z + sclera_ry * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]

        for i in range(n):
            j = (i + 1) % n

            # Pupil fan triangles (slot 0)
            if x_sign > 0:
                f = bm.faces.new([center_v, pupil_vs[i], pupil_vs[j]])
            else:
                f = bm.faces.new([center_v, pupil_vs[j], pupil_vs[i]])
            f.material_index = 0

            # Iris ring quads (slot 1)
            if x_sign > 0:
                f = bm.faces.new([pupil_vs[i], iris_vs[i], iris_vs[j], pupil_vs[j]])
            else:
                f = bm.faces.new([pupil_vs[j], iris_vs[j], iris_vs[i], pupil_vs[i]])
            f.material_index = 1

            # Sclera ring quads (slot 2)
            if x_sign > 0:
                f = bm.faces.new([iris_vs[i], sclera_vs[i], sclera_vs[j], iris_vs[j]])
            else:
                f = bm.faces.new([iris_vs[j], sclera_vs[j], sclera_vs[i], iris_vs[i]])
            f.material_index = 2

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    eye_mesh = bpy.data.meshes.new("Eye_Disc_Mesh")
    bm.to_mesh(eye_mesh)
    eye_mesh.update()
    bm.free()

    eye_obj = bpy.data.objects.new("Eyes_Disc", eye_mesh)
    bpy.context.collection.objects.link(eye_obj)

    # Slot 0 — Pupil
    pupil_mat = bpy.data.materials.new("Eye_Pupil")
    pupil_mat.use_nodes = True
    bsdf = pupil_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.05
        _set_specular(bsdf, 0.9)
    eye_obj.data.materials.append(pupil_mat)

    # Slot 1 — Iris
    iris_mat = bpy.data.materials.new("Eye_Iris")
    iris_mat.use_nodes = True
    bsdf = iris_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = iris_rgba
        bsdf.inputs["Roughness"].default_value = 0.15
        _set_specular(bsdf, 0.6)
    eye_obj.data.materials.append(iris_mat)

    # Slot 2 — Sclera (off-white)
    sclera_mat = bpy.data.materials.new("Eye_Sclera")
    sclera_mat.use_nodes = True
    bsdf = sclera_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.92, 0.90, 0.88, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.40
        _set_specular(bsdf, 0.2)
    eye_obj.data.materials.append(sclera_mat)

    return [eye_obj]


def create_eyebrows(head_z, head_r, face_y=None, brow_color=None):
    """Build low-poly eyebrow strips sitting just above the eye sockets.

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

    # Brow sits immediately above the top of the eye socket
    brow_z      = eye_z + eye_r + head_r * 0.015   # bottom edge of brow
    brow_h      = head_r * 0.028                    # strip height (Z)
    brow_half_w = head_r * 0.18                     # half-width of each brow
    brow_y      = disc_y                            # same depth as eye surface
    n_segs      = 5

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
