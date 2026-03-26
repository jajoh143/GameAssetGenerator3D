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
_EYE_FORWARD = 0.10   # disc protrudes 10 % of horizontal head radius forward


def _eye_geometry(head_z, head_r, face_y, head_r_horiz=None):
    """Return (eye_r, eye_x, eye_z, eye_y, disc_y) for the current head.

    Args:
        head_z:       Z of the head CENTRE (midpoint between chin and crown).
        head_r:       Vertical head HALF-HEIGHT (crown − centre).
        head_r_horiz: Horizontal head half-width — used for eye_r and eye_x
                      sizing so eyes scale with the actual head width.
                      Falls back to head_r when None.
        face_y:       Most-forward Y of the face at eye level (from vertex
                      sampling in template_mesh).  Eyes are placed at this
                      Y, with a small forward nudge so they sit on the surface.
    """
    hr_h   = head_r_horiz if head_r_horiz is not None else head_r
    eye_r  = hr_h * 0.22           # big expressive cartoon eyes
    eye_z  = head_z - head_r * 0.30  # well below head centre, in the face zone
    eye_x  = hr_h * 0.32           # lateral separation scales with head width

    if face_y is not None:
        # Place disc slightly forward of (in front of) the face surface
        disc_y = face_y - hr_h * _EYE_FORWARD
    else:
        # Fallback: spherical approximation (NBM-era behaviour)
        disc_y = -(hr_h * 0.62)

    eye_y = disc_y - eye_r
    print(f"[eyes] eye_z={eye_z:.4f}, eye_x={eye_x:.4f}, eye_r={eye_r:.4f}, disc_y={disc_y:.4f}")
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

    # Oval proportions — slightly wider than tall for cartoon look
    rx = eye_r * 1.25
    ry = eye_r * 1.05
    n  = 10  # smoother disc with more segments

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
        bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.02, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        # Completely matte — no specular at all
        bsdf.inputs["Specular IOR Level"].default_value = 0.0
        # Subtle self-emission so the black is consistent and never shows
        # edge lighting that creates a "ring" or "goggle" artifact
        bsdf.inputs["Emission Color"].default_value = (0.02, 0.02, 0.03, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 0.5
    eye_obj.data.materials.append(mat)

    # ── White highlight dots ────────────────────────────────────────
    bm2 = bmesh_mod.new()
    highlight_r = eye_r * 0.18  # small glint, not so big it makes eyes look hollow
    hl_n = 6
    for x_sign in (1, -1):
        cx = x_sign * eye_x + rx * 0.35  # clearly in upper-right corner
        hz = eye_z + ry * 0.45           # high in the eye for anime-style glint
        hy = disc_y - highlight_r * 0.8   # well in front of eye disc
        center_h = bm2.verts.new((cx, hy, hz))
        ring_h = [
            bm2.verts.new((
                cx + highlight_r * math.cos(2 * math.pi * i / hl_n),
                hy,
                hz + highlight_r * math.sin(2 * math.pi * i / hl_n),
            ))
            for i in range(hl_n)
        ]
        for i in range(hl_n):
            j = (i + 1) % hl_n
            try:
                if x_sign > 0:
                    bm2.faces.new([center_h, ring_h[i], ring_h[j]])
                else:
                    bm2.faces.new([center_h, ring_h[j], ring_h[i]])
            except ValueError:
                pass
    bmesh_mod.ops.recalc_face_normals(bm2, faces=bm2.faces)
    hl_mesh = bpy.data.meshes.new("Eye_Highlight_Mesh")
    bm2.to_mesh(hl_mesh)
    hl_mesh.update()
    bm2.free()
    hl_obj = bpy.data.objects.new("Eye_Highlights", hl_mesh)
    bpy.context.collection.objects.link(hl_obj)
    hl_mat = bpy.data.materials.new("Eye_Highlight_Mat")
    hl_mat.use_nodes = True
    hl_bsdf = hl_mat.node_tree.nodes.get("Principled BSDF")
    if hl_bsdf:
        hl_bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        hl_bsdf.inputs["Roughness"].default_value = 0.0
        hl_bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        hl_bsdf.inputs["Emission Strength"].default_value = 2.0
    hl_obj.data.materials.append(hl_mat)

    return [eye_obj, hl_obj]


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
    """Build a low-poly cartoon nose — rounded dome protruding from face centre.

    Uses a half-sphere shape (8 segments) for a soft, cartoony look rather than
    a sharp pyramid.  The nose is large enough to read at game camera distance.

    Args:
        head_z:       Z of the head equator.
        head_r:       Vertical head radius.
        head_r_horiz: Horizontal head half-width — used for nose sizing.
        face_y:       Face-surface Y at eye level (from vertex sampling).
        skin_tone:    RGBA tuple or None (defaults to neutral skin).

    Returns:
        nose_obj — one bpy.types.Object.
    """
    import bpy
    import bmesh as bmesh_mod

    hr_h = head_r_horiz if head_r_horiz is not None else head_r

    # head_z is now the centre of the head; nose sits between eyes and mouth
    nz       = head_z - head_r * 0.42        # slightly higher for better visibility
    # Face surface curves inward below the eyes, so we push the nose
    # out extra far to clear the mesh at this lower Z level.
    base_y   = (face_y - hr_h * 0.08) if face_y is not None else -(hr_h * 0.62)
    nose_r   = hr_h * 0.20                   # big cartoon nose — must read from front view
    protrude = hr_h * 0.50                   # very prominent forward protrusion
    print(f"[nose] nz={nz:.4f}, base_y={base_y:.4f}, tip_y={base_y - protrude:.4f}, nose_r={nose_r:.4f}")

    # Build a half-sphere dome (8 segments, 3 latitude rings + tip)
    n_seg = 8
    n_lat = 3  # number of latitude rings

    bm = bmesh_mod.new()

    # Base ring sits on the face surface
    base_ring = []
    for i in range(n_seg):
        angle = 2 * math.pi * i / n_seg
        x = nose_r * math.cos(angle)
        z = nz + nose_r * 0.8 * math.sin(angle)  # slightly taller than wide
        base_ring.append(bm.verts.new((x, base_y, z)))

    # Intermediate latitude rings
    rings = [base_ring]
    for lat in range(1, n_lat + 1):
        t = lat / (n_lat + 1)  # 0→1 from base to tip
        ring_r = nose_r * (1.0 - t * 0.6)  # radius shrinks toward tip
        ring_y = base_y - protrude * t      # moves forward
        ring_z_offset = nose_r * 0.15 * t   # rises slightly toward bridge
        ring = []
        for i in range(n_seg):
            angle = 2 * math.pi * i / n_seg
            x = ring_r * math.cos(angle)
            z = nz + ring_z_offset + ring_r * 0.8 * math.sin(angle)
            ring.append(bm.verts.new((x, ring_y, z)))
        rings.append(ring)

    # Tip vertex
    tip = bm.verts.new((0, base_y - protrude, nz + nose_r * 0.2))

    # Bridge rings together
    for r_idx in range(len(rings) - 1):
        r_a, r_b = rings[r_idx], rings[r_idx + 1]
        for i in range(n_seg):
            j = (i + 1) % n_seg
            try:
                bm.faces.new([r_a[i], r_a[j], r_b[j], r_b[i]])
            except ValueError:
                pass

    # Close tip with triangle fan
    last_ring = rings[-1]
    for i in range(n_seg):
        j = (i + 1) % n_seg
        try:
            bm.faces.new([last_ring[i], last_ring[j], tip])
        except ValueError:
            pass

    # Cap the base (back face flush with skin)
    try:
        bm.faces.new(list(reversed(base_ring)))
    except ValueError:
        pass

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_n = bpy.data.meshes.new("Nose_Mesh")
    bm.to_mesh(mesh_n)
    mesh_n.update()
    bm.free()

    nose_obj = bpy.data.objects.new("Nose", mesh_n)
    bpy.context.collection.objects.link(nose_obj)

    # Smooth shade for a soft rounded look
    bpy.context.view_layer.objects.active = nose_obj
    nose_obj.select_set(True)
    bpy.ops.object.shade_smooth()
    nose_obj.select_set(False)

    mat = bpy.data.materials.new("Nose_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Noticeably pinker than base skin so nose reads as distinct
        if skin_tone:
            r, g, b, a = skin_tone
            color = (min(r * 1.15, 1.0), g * 0.80, b * 0.72, 1.0)
        else:
            color = (0.75, 0.48, 0.38, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.45
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
    nose_obj.data.materials.append(mat)

    return nose_obj


def create_mouth(head_z, head_r, face_y=None, head_r_horiz=None, skin_tone=None):
    """Build a visible, curved cartoon mouth with upper and lower lips.

    The mouth is built as a smooth curved strip with multiple segments for
    a friendly smile shape.  Both lips have distinct pinkish-red colouring
    that reads clearly against the skin, and enough forward protrusion to
    catch light from the 3-point setup.

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
    import math

    hr_h = head_r_horiz if head_r_horiz is not None else head_r

    # Position: below nose, in the lower third of the head
    # head_z is the centre of the head; mouth sits well below centre
    mz_centre = head_z - head_r * 0.62
    # Face curves sharply inward at chin level — push mouth way forward
    base_y    = (face_y - hr_h * 0.10) if face_y is not None else -(hr_h * 0.62)
    protrude  = hr_h * 0.40            # very prominent — must clear face mesh
    print(f"[mouth] mz={mz_centre:.4f}, base_y={base_y:.4f}, protrude={protrude:.4f}")

    # Sizing — big and visible, proportional to full head width
    half_w    = hr_h * 0.28            # wide smile
    upper_h   = head_r * 0.14          # tall upper lip (was 0.06 — invisible)
    lower_h   = head_r * 0.16          # tall lower lip (was 0.07 — invisible)
    gap       = head_r * 0.012         # visible dark line between lips
    n_seg     = 8                      # segments along the smile curve

    bm = bmesh_mod.new()

    # Helper: generate a row of vertices along a smile arc.
    # x sweeps from -half_w to +half_w.  The smile_curve lifts the
    # corners slightly (cosine ease) to give a gentle upward curl.
    def _arc_row(z_base, y_off, smile_lift, n):
        """Return a list of n+1 verts along a horizontal smile arc."""
        verts = []
        for i in range(n + 1):
            t = i / n                       # 0 → 1 across the mouth
            x = -half_w + 2 * half_w * t
            # Cosine curve: centre is lowest, corners lift up
            curve = smile_lift * (math.cos(math.pi * t) * -0.5 + 0.5)
            z = z_base + curve
            # Protrusion peaks at centre, tapers at corners
            bulge = protrude * math.cos(math.pi * 0.5 * (2 * t - 1))
            y = base_y - bulge + y_off
            verts.append(bm.verts.new((x, y, z)))
        return verts

    # Build four vertex rows (top of upper → seam → seam → bottom of lower)
    smile_lift = head_r * 0.03   # how much corners curl up
    row_upper_top = _arc_row(mz_centre + gap * 0.5 + upper_h, 0.0,        smile_lift, n_seg)
    row_upper_bot = _arc_row(mz_centre + gap * 0.5,           0.0,        smile_lift * 0.5, n_seg)
    row_lower_top = _arc_row(mz_centre - gap * 0.5,           0.0,        smile_lift * 0.5, n_seg)
    row_lower_bot = _arc_row(mz_centre - gap * 0.5 - lower_h, protrude * 0.15, smile_lift * 0.3, n_seg)

    # Stitch quads between adjacent rows
    def _stitch(row_a, row_b):
        for i in range(len(row_a) - 1):
            try:
                bm.faces.new([row_a[i], row_a[i + 1], row_b[i + 1], row_b[i]])
            except ValueError:
                pass

    _stitch(row_upper_top, row_upper_bot)   # upper lip surface
    _stitch(row_lower_top, row_lower_bot)   # lower lip surface

    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_m = bpy.data.meshes.new("Mouth_Mesh")
    bm.to_mesh(mesh_m)
    mesh_m.update()
    bm.free()

    mouth_obj = bpy.data.objects.new("Mouth", mesh_m)
    bpy.context.collection.objects.link(mouth_obj)

    # Smooth shading for a soft, rounded look
    bpy.context.view_layer.objects.active = mouth_obj
    mouth_obj.select_set(True)
    bpy.ops.object.shade_smooth()
    mouth_obj.select_set(False)

    # Warm rosy-pink lip colour — clearly distinct from surrounding skin
    mat = bpy.data.materials.new("Mouth_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if skin_tone:
            r, g, b, a = skin_tone
            # Strong rosy red — clearly distinct from skin at any distance
            lip_color = (min(r * 1.20, 1.0), g * 0.40, b * 0.35, 1.0)
        else:
            lip_color = (0.82, 0.30, 0.28, 1.0)
        bsdf.inputs["Base Color"].default_value = lip_color
        bsdf.inputs["Roughness"].default_value  = 0.42
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
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

    # Z band: between nose and mouth (head_z is now head centre)
    mz_top = head_z - head_r * 0.55
    mz_bot = head_z - head_r * 0.65
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
