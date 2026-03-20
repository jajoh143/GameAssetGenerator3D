"""Low-poly 3-part eye generation for the humanoid pipeline.

Each eye is built from three separate mesh objects:
  • Sclera  – white of the eye (UV sphere, ~40 faces per eye, 80 total)
  • Iris    – coloured pupil + iris disc (~24 faces per eye, 48 total)
  • Cornea  – near-transparent glossy dome (~40 faces per eye, 80 total)

Total eye geometry: ~208 faces (both eyes, all 3 parts).

Public interface
----------------
  create_eyes(head_z, head_r, eye_color, face_y)  →  [sclera_obj, iris_obj, cornea_obj]
  create_eyebrows(head_z, head_r, face_y, brow_color)  →  brow_obj
"""

import math

# ── Shared geometry constants ─────────────────────────────────────────────────

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
    """Build full 3-part eyes (sclera + iris + cornea) for left and right.

    Geometry layout
    ---------------
    Sclera:  opaque off-white UV sphere.
    Iris:    flat two-zone disc (pupil centre + coloured ring) placed just in
             front of the sclera tip so it is never occluded.  Two material
             slots: slot 0 = pupil (near-black), slot 1 = iris (eye_color).
    Cornea:  slightly larger transparent sphere (IOR 1.4) that encloses both
             sclera and iris, giving a wet-eye gloss effect.

    Args:
        head_z:    Z of the head centre.
        head_r:    Head radius in metres.
        eye_color: RGBA or RGB tuple for iris colour, or None (defaults to warm brown).
        face_y:    Most-forward Y of the body mesh (nose-tip bounding-box Y).

    Returns:
        [sclera_obj, iris_obj, cornea_obj]  — three bpy.types.Object instances,
        each containing geometry for both left and right eyes (~208 faces total).
    """
    import bpy
    import bmesh as bmesh_mod
    import mathutils

    eye_r, eye_x, eye_z, eye_y, _ = _eye_geometry(head_z, head_r, face_y)
    iris_rgba = _default_iris_color(eye_color)

    iris_r   = eye_r * 0.50          # iris covers ~50 % of sclera radius
    pupil_r  = iris_r * 0.38         # pupil ~38 % of iris radius
    # Place iris disc just in front of the sclera's frontmost point so the
    # opaque sclera never occludes it.  The cornea (1.02× radius) then wraps
    # over everything.
    iris_y   = eye_y - eye_r * 1.005
    cornea_r = eye_r * 1.020

    # ── 1. SCLERA ──────────────────────────────────────────────────────────────
    bm = bmesh_mod.new()
    for x_sign in (1, -1):
        bmesh_mod.ops.create_uvsphere(
            bm,
            u_segments=8,
            v_segments=6,
            radius=eye_r,
            matrix=mathutils.Matrix.Translation((x_sign * eye_x, eye_y, eye_z)),
            calc_uvs=False,
        )
    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    sclera_mesh = bpy.data.meshes.new("Sclera_Mesh")
    bm.to_mesh(sclera_mesh)
    sclera_mesh.update()
    bm.free()

    sclera_obj = bpy.data.objects.new("Eyes_Sclera", sclera_mesh)
    bpy.context.collection.objects.link(sclera_obj)
    for poly in sclera_mesh.polygons:
        poly.use_smooth = True

    sclera_mat = bpy.data.materials.new("Eye_Sclera")
    sclera_mat.use_nodes = True
    bsdf = sclera_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.95, 0.93, 0.90, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.30
        _set_specular(bsdf, 0.4)
    sclera_obj.data.materials.append(sclera_mat)

    # ── 2. IRIS + PUPIL ────────────────────────────────────────────────────────
    # Two-zone fan disc: center → pupil_r (slot 0 = pupil) and
    # pupil_r → iris_r (slot 1 = iris colour).
    bm = bmesh_mod.new()
    n = 12
    for x_sign in (1, -1):
        cx = x_sign * eye_x
        center_v = bm.verts.new((cx, iris_y, eye_z))
        inner_vs = [
            bm.verts.new((
                cx + pupil_r * math.cos(2 * math.pi * i / n),
                iris_y,
                eye_z + pupil_r * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]
        outer_vs = [
            bm.verts.new((
                cx + iris_r * math.cos(2 * math.pi * i / n),
                iris_y,
                eye_z + iris_r * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]

        for i in range(n):
            j = (i + 1) % n
            # Pupil triangle — winding reversed for left eye so normal faces -Y
            if x_sign > 0:
                f = bm.faces.new([center_v, inner_vs[i], inner_vs[j]])
            else:
                f = bm.faces.new([center_v, inner_vs[j], inner_vs[i]])
            f.material_index = 0

            # Iris quad
            if x_sign > 0:
                f = bm.faces.new([inner_vs[i], outer_vs[i], outer_vs[j], inner_vs[j]])
            else:
                f = bm.faces.new([inner_vs[j], outer_vs[j], outer_vs[i], inner_vs[i]])
            f.material_index = 1

    iris_mesh = bpy.data.meshes.new("Iris_Mesh")
    bm.to_mesh(iris_mesh)
    iris_mesh.update()
    bm.free()

    iris_obj = bpy.data.objects.new("Eyes_Iris", iris_mesh)
    bpy.context.collection.objects.link(iris_obj)

    pupil_mat = bpy.data.materials.new("Eye_Pupil")
    pupil_mat.use_nodes = True
    bsdf = pupil_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.05
        _set_specular(bsdf, 0.9)
    iris_obj.data.materials.append(pupil_mat)

    iris_mat = bpy.data.materials.new("Eye_Iris")
    iris_mat.use_nodes = True
    bsdf = iris_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = iris_rgba
        bsdf.inputs["Roughness"].default_value = 0.10
        _set_specular(bsdf, 0.7)
    iris_obj.data.materials.append(iris_mat)

    # ── 3. CORNEA ──────────────────────────────────────────────────────────────
    bm = bmesh_mod.new()
    for x_sign in (1, -1):
        bmesh_mod.ops.create_uvsphere(
            bm,
            u_segments=8,
            v_segments=6,
            radius=cornea_r,
            matrix=mathutils.Matrix.Translation((x_sign * eye_x, eye_y, eye_z)),
            calc_uvs=False,
        )
    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    cornea_mesh = bpy.data.meshes.new("Cornea_Mesh")
    bm.to_mesh(cornea_mesh)
    cornea_mesh.update()
    bm.free()

    cornea_obj = bpy.data.objects.new("Eyes_Cornea", cornea_mesh)
    bpy.context.collection.objects.link(cornea_obj)
    for poly in cornea_mesh.polygons:
        poly.use_smooth = True

    cornea_mat = bpy.data.materials.new("Eye_Cornea")
    cornea_mat.use_nodes = True
    bsdf = cornea_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.0
        _set_specular(bsdf, 1.0)
        if "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 1.0
        elif "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = 1.0
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = 1.4
    try:
        cornea_mat.blend_method = 'BLEND'
    except AttributeError:
        pass  # Blender 4.2+ handles transparency differently
    cornea_obj.data.materials.append(cornea_mat)

    return [sclera_obj, iris_obj, cornea_obj]


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
