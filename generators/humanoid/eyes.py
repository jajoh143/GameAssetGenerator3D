"""Low-poly flat-disc eye generation for the humanoid pipeline.

Each eye is a single flat black oval — a simple triangle fan.  No
sclera/iris/pupil zones; just one opaque black disc per eye.

Both eyes share one mesh object (Eyes_Disc) with a single material slot.
Total eye geometry: ~16 faces (both eyes, 8 triangles × 2 eyes).

Public interface
----------------
  create_eyes(head_z, head_r, eye_color, face_y)  →  [eye_disc_obj]
  create_eyebrows(head_z, head_r, face_y, brow_color)  →  brow_obj
  create_nose(head_z, head_r, face_y, head_r_horiz, skin_tone)  →  nose_obj
  create_mouth(head_z, head_r, face_y, head_r_horiz, skin_tone)  →  mouth_obj
  create_mustache(head_z, head_r, face_y, head_r_horiz, mustache_color)  →  mustache_obj
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
    eye_r  = hr_h * 0.075          # scales with horizontal head width
    eye_z  = head_z - head_r * 0.08  # slightly below equator
    eye_x  = hr_h * 0.26           # lateral separation scales with head width

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


def create_nose(head_z, head_r, face_y=None, head_r_horiz=None, skin_tone=None):
    """Build a low-poly cartoon nose — small pyramid protruding from face centre.

    Args:
        head_z:       Z of the head equator.
        head_r:       Vertical head radius.
        head_r_horiz: Horizontal head half-width — used for nose sizing.
        face_y:       Face-surface Y at eye level (from vertex sampling).
        skin_tone:    RGBA tuple or None (defaults to neutral skin).

    Returns:
        nose_obj — one bpy.types.Object (5 faces).
    """
    import bpy
    import bmesh as bmesh_mod

    hr_h = head_r_horiz if head_r_horiz is not None else head_r

    nz       = head_z - head_r * 0.38        # below equator = nose level
    base_y   = (face_y - hr_h * 0.01) if face_y is not None else -(hr_h * 0.62)
    tip_y    = base_y - hr_h * 0.12          # tip protrudes forward (more prominent)
    nw       = hr_h  * 0.075                 # nose half-width (wider)
    nh       = head_r * 0.115                # nose half-height (taller)

    bm = bmesh_mod.new()
    bl  = bm.verts.new((-nw, base_y, nz - nh))
    br  = bm.verts.new(( nw, base_y, nz - nh))
    tl  = bm.verts.new((-nw, base_y, nz + nh))
    tr  = bm.verts.new(( nw, base_y, nz + nh))
    tip = bm.verts.new(( 0,  tip_y,  nz))

    for fv in [
        [bl, br, tip],       # bottom slope
        [tr, tl, tip],       # top slope
        [tl, bl, tip],       # left slope
        [br, tr, tip],       # right slope
        [bl, tl, tr, br],    # back face (flush with face surface)
    ]:
        try:
            bm.faces.new(fv)
        except ValueError:
            pass

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_n = bpy.data.meshes.new("Nose_Mesh")
    bm.to_mesh(mesh_n)
    mesh_n.update()
    bm.free()

    nose_obj = bpy.data.objects.new("Nose", mesh_n)
    bpy.context.collection.objects.link(nose_obj)

    mat = bpy.data.materials.new("Nose_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        color = skin_tone if skin_tone else (0.65, 0.55, 0.45, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.69
    nose_obj.data.materials.append(mat)

    return nose_obj


def create_mouth(head_z, head_r, face_y=None, head_r_horiz=None, skin_tone=None):
    """Build a simple low-poly cartoon mouth — two lips as flat quads.

    Args:
        head_z:       Z of the head equator.
        head_r:       Vertical head radius.
        head_r_horiz: Horizontal head half-width.
        face_y:       Face-surface Y at eye level.
        skin_tone:    RGBA tuple or None (used for skin-coloured lip base).

    Returns:
        mouth_obj — one bpy.types.Object.
    """
    import bpy
    import bmesh as bmesh_mod

    hr_h = head_r_horiz if head_r_horiz is not None else head_r

    # Mouth sits below nose, ~60 % of the way to the chin
    mz       = head_z - head_r * 0.70
    base_y   = (face_y - hr_h * 0.005) if face_y is not None else -(hr_h * 0.62)
    lip_y    = base_y - hr_h * 0.04   # lips protrude slightly
    mw       = hr_h * 0.140           # half-width (smile width)
    upper_h  = head_r * 0.030         # upper-lip height
    lower_h  = head_r * 0.040         # lower-lip height (slightly fuller)
    gap      = head_r * 0.006         # dark gap between lips

    bm = bmesh_mod.new()

    # Upper lip — 4 vertices, slightly arched (centre lower for cupid's bow)
    u_bl = bm.verts.new((-mw,     base_y, mz + gap * 0.5))
    u_br = bm.verts.new(( mw,     base_y, mz + gap * 0.5))
    u_tl = bm.verts.new((-mw,     lip_y,  mz + gap * 0.5 + upper_h))
    u_tr = bm.verts.new(( mw,     lip_y,  mz + gap * 0.5 + upper_h))
    u_mc = bm.verts.new(( 0,      lip_y,  mz + gap * 0.5 + upper_h * 0.55))  # centre dip
    try:
        bm.faces.new([u_bl, u_br, u_tr, u_tl])
    except ValueError:
        pass

    # Lower lip
    l_tl = bm.verts.new((-mw,     base_y, mz - gap * 0.5))
    l_tr = bm.verts.new(( mw,     base_y, mz - gap * 0.5))
    l_bl = bm.verts.new((-mw * 0.85, lip_y,  mz - gap * 0.5 - lower_h))
    l_br = bm.verts.new(( mw * 0.85, lip_y,  mz - gap * 0.5 - lower_h))
    try:
        bm.faces.new([l_tl, l_tr, l_br, l_bl])
    except ValueError:
        pass

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_m = bpy.data.meshes.new("Mouth_Mesh")
    bm.to_mesh(mesh_m)
    mesh_m.update()
    bm.free()

    mouth_obj = bpy.data.objects.new("Mouth", mesh_m)
    bpy.context.collection.objects.link(mouth_obj)

    # Warm pinkish lip colour — slightly darker/redder than skin
    mat = bpy.data.materials.new("Mouth_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if skin_tone:
            r, g, b, a = skin_tone
            lip_color = (r * 0.82, g * 0.60, b * 0.58, 1.0)
        else:
            lip_color = (0.72, 0.40, 0.38, 1.0)
        bsdf.inputs["Base Color"].default_value = lip_color
        bsdf.inputs["Roughness"].default_value  = 0.55
    mouth_obj.data.materials.append(mat)

    return mouth_obj


def create_mustache(head_z, head_r, face_y=None, head_r_horiz=None,
                    mustache_color=None):
    """Build a low-poly cartoon mustache — two curved wings flanking centre.

    The mustache sits between the nose tip and upper lip, protrudes slightly
    forward from the face surface.  Two flat quad wings (left + right) meet
    at a narrow centre gap, giving the classic "chevron" / Freddie Mercury look.

    Args:
        head_z:          Z of the head equator.
        head_r:          Vertical head radius in metres.
        head_r_horiz:    Horizontal head half-width for sizing.
        face_y:          Face-surface Y at eye level (from vertex sampling).
        mustache_color:  RGBA tuple or None (defaults to dark brown).

    Returns:
        mustache_obj — one bpy.types.Object (~4 faces).
    """
    import bpy
    import bmesh as bmesh_mod

    hr_h = head_r_horiz if head_r_horiz is not None else head_r

    color = tuple(mustache_color) if mustache_color else (0.12, 0.07, 0.04, 1.0)

    # Z band: just below nose (~47%), above upper lip (~56%)
    mz_top = head_z - head_r * 0.46
    mz_bot = head_z - head_r * 0.58
    mh = mz_top - mz_bot

    base_y = (face_y - hr_h * 0.005) if face_y is not None else -(hr_h * 0.62)
    tip_y  = base_y - hr_h * 0.065     # protrudes forward

    # Geometry: two wings meeting at a tiny centre gap
    mw       = hr_h * 0.155   # outer half-width of each wing
    mw_inner = hr_h * 0.018   # inner gap from centre

    bm = bmesh_mod.new()

    for x_sign in (1, -1):
        xi = x_sign * mw_inner
        xo = x_sign * mw
        # Inner edge is flush (base_y); outer corner droops for curved look
        ti = bm.verts.new((xi, base_y, mz_top))
        to = bm.verts.new((xo, base_y, mz_top))
        bi = bm.verts.new((xi, tip_y,  mz_bot + mh * 0.15))   # inner bottom — slight lift
        bo = bm.verts.new((xo, tip_y,  mz_bot))               # outer corner — lower

        try:
            if x_sign > 0:
                bm.faces.new([ti, to, bo, bi])
            else:
                bm.faces.new([to, ti, bi, bo])
        except ValueError:
            pass

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_mu = bpy.data.meshes.new("Mustache_Mesh")
    bm.to_mesh(mesh_mu)
    mesh_mu.update()
    bm.free()

    mobj = bpy.data.objects.new("Mustache", mesh_mu)
    bpy.context.collection.objects.link(mobj)

    mat = bpy.data.materials.new("Mustache_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.85
    mobj.data.materials.append(mat)

    return mobj
