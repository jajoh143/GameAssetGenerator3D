"""Low-poly eye generation for the humanoid pipeline.

Each eye is two objects combined into one draw call per material:
  • Eyeballs_Mesh  — two low-poly spheres (sclera), ~32 faces each
  • Iris_Mesh      — two flat discs (iris ring + pupil) per eye, ~16 faces each

Total budget: ≈ 96 extra faces for the pair.

Public interface
----------------
  create_eyes(head_z, head_r, eye_color)  →  [eyeballs_obj, iris_obj]
  EYE_COLORS  — dict mapping name → RGBA tuple
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


def create_eyes(head_z, head_r, eye_color=None):
    """Build both eyeballs and iris/pupil geometry, returning two mesh objects.

    Args:
        head_z:     Z of the brow/hairline level (same value passed to create_hair).
        head_r:     Head radius in metres  (= actual_height * 0.065).
        eye_color:  Iris colour — RGBA tuple, a key from EYE_COLORS, or None.

    Returns:
        [eyeballs_obj, iris_obj]  — two linked bpy.types.Object instances.
    """
    import bpy
    import bmesh as bmesh_mod
    import mathutils

    # ── Colour resolution ────────────────────────────────────────────────────
    if eye_color is None:
        iris_rgba = EYE_COLORS["brown"]
    elif isinstance(eye_color, str):
        iris_rgba = EYE_COLORS.get(eye_color, EYE_COLORS["brown"])
    else:
        iris_rgba = tuple(eye_color)

    sclera_rgba = (0.92, 0.90, 0.88, 1.0)
    pupil_rgba  = (0.04, 0.03, 0.03, 1.0)  # near-black pupil centre

    # ── Geometry constants ───────────────────────────────────────────────────
    eye_r    = head_r * 0.115      # eyeball sphere radius
    eye_z    = head_z - head_r * 0.15   # slightly below brow
    eye_x    = head_r * 0.32       # lateral half-gap between eye centres
    # Centre spheres so they sit ~40 % inside the head face (protrude visibly)
    eye_y    = -(head_r * 0.85)    # sphere centre y (head face ≈ -head_r)

    iris_r   = eye_r * 0.68        # iris disc radius
    pupil_r  = iris_r * 0.48       # pupil disc radius (solid dark centre)
    # Iris / pupil disc sits at the near-front pole of the eyeball sphere
    disc_y   = eye_y - eye_r * 0.88

    # ── Eyeball spheres ──────────────────────────────────────────────────────
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

    sclera_mat = bpy.data.materials.new("Eye_Sclera")
    sclera_mat.use_nodes = True
    bsdf = sclera_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = sclera_rgba
        bsdf.inputs["Roughness"].default_value = 0.25
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.5
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.5
    eyes_obj.data.materials.append(sclera_mat)

    # ── Iris ring + pupil discs ──────────────────────────────────────────────
    # Each eye has:
    #   • An annular ring  (outer iris colour)  between pupil_r and iris_r
    #   • A filled disc    (pupil near-black)    inside pupil_r
    # Both lie in the XZ plane (facing -Y) at disc_y.
    bm2 = bmesh_mod.new()
    n = 10   # polygon sides — enough for smooth circles at this size

    for x_sign in (1, -1):
        cx = x_sign * eye_x

        # Outer iris ring vertices
        inner_v = [
            bm2.verts.new((
                cx + pupil_r * math.cos(2 * math.pi * i / n),
                disc_y,
                eye_z + pupil_r * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]
        outer_v = [
            bm2.verts.new((
                cx + iris_r * math.cos(2 * math.pi * i / n),
                disc_y,
                eye_z + iris_r * math.sin(2 * math.pi * i / n),
            ))
            for i in range(n)
        ]
        for i in range(n):
            j = (i + 1) % n
            try:
                bm2.faces.new([outer_v[i], outer_v[j], inner_v[j], inner_v[i]])
            except ValueError:
                pass

        # Pupil filled disc
        ctr = bm2.verts.new((cx, disc_y, eye_z))
        for i in range(n):
            j = (i + 1) % n
            try:
                bm2.faces.new([ctr, inner_v[i], inner_v[j]])
            except ValueError:
                pass

    bmesh_mod.ops.recalc_face_normals(bm2, faces=bm2.faces)

    mesh_i = bpy.data.meshes.new("Iris_Mesh")
    bm2.to_mesh(mesh_i)
    mesh_i.update()
    bm2.free()

    iris_obj = bpy.data.objects.new("Iris", mesh_i)
    bpy.context.collection.objects.link(iris_obj)

    # Iris uses same material for both iris ring and pupil — split into two
    # materials so the two regions can have distinct colours.
    # Material slot 0 = iris ring, slot 1 = pupil.
    iris_mat = bpy.data.materials.new("Eye_Iris")
    iris_mat.use_nodes = True
    bsdf2 = iris_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf2:
        bsdf2.inputs["Base Color"].default_value = iris_rgba
        bsdf2.inputs["Roughness"].default_value = 0.20
        if "Specular IOR Level" in bsdf2.inputs:
            bsdf2.inputs["Specular IOR Level"].default_value = 0.60
        elif "Specular" in bsdf2.inputs:
            bsdf2.inputs["Specular"].default_value = 0.60
    iris_obj.data.materials.append(iris_mat)

    pupil_mat = bpy.data.materials.new("Eye_Pupil")
    pupil_mat.use_nodes = True
    bsdf3 = pupil_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf3:
        bsdf3.inputs["Base Color"].default_value = pupil_rgba
        bsdf3.inputs["Roughness"].default_value = 0.05   # very glossy — wet
        if "Specular IOR Level" in bsdf3.inputs:
            bsdf3.inputs["Specular IOR Level"].default_value = 0.90
        elif "Specular" in bsdf3.inputs:
            bsdf3.inputs["Specular"].default_value = 0.90
    iris_obj.data.materials.append(pupil_mat)

    # Assign pupil material (slot 1) to the inner pupil faces.
    # Iris ring faces were created first (first n*10 faces per eye),
    # so pupil tris follow in each eye's geometry block.
    iris_obj.data.update()
    face_idx = 0
    for _eye in range(2):        # two eyes
        # n ring quads → iris material (slot 0, default)
        face_idx += n
        # n pupil tris → pupil material (slot 1)
        for fi in range(face_idx, face_idx + n):
            if fi < len(iris_obj.data.polygons):
                iris_obj.data.polygons[fi].material_index = 1
        face_idx += n

    return [eyes_obj, iris_obj]
