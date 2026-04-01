"""LED rainbow neon sign mesh construction.

Builds the sign from three components:
  1. Backing panel  — dark metal rectangular slab
  2. Emissive tubes — rainbow arcs, flat bars, or word strip depending on variation
  3. Mounting brackets — two small metal cylinders on the rear

All geometry is centered at origin with the panel face toward +Y.
Feet of the sign rest at Z = 0 (panel bottom edge).
"""

import bpy
import bmesh
import math

from generators.base import BaseAssetGenerator

# Bind base utilities as module-level names for convenience
_clear_scene = BaseAssetGenerator._clear_scene
_join = BaseAssetGenerator._join
_finalize = BaseAssetGenerator._finalize
_apply_material = BaseAssetGenerator._apply_material
_apply_emission_material = BaseAssetGenerator._apply_emission_material

# ROYGBIV palette — one entry per rainbow stripe
RAINBOW_COLORS = [
    (1.0, 0.0, 0.0, 1.0),   # Red
    (1.0, 0.5, 0.0, 1.0),   # Orange
    (1.0, 1.0, 0.0, 1.0),   # Yellow
    (0.0, 1.0, 0.0, 1.0),   # Green
    (0.0, 0.4, 1.0, 1.0),   # Blue
    (0.3, 0.0, 0.8, 1.0),   # Indigo
    (0.6, 0.0, 1.0, 1.0),   # Violet
]

COLOR_NAMES = ["Red", "Orange", "Yellow", "Green", "Blue", "Indigo", "Violet"]


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

def _build_panel(cfg, style):
    """Create the rectangular backing panel (dark near-black metal slab)."""
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, h / 2))
    panel = bpy.context.active_object
    panel.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    panel.name = "Panel"

    _apply_material(
        panel, style, "PanelMetal",
        color=(0.05, 0.05, 0.05, 1.0),
        roughness=0.6,
        metallic=0.8,
    )
    return panel


# ---------------------------------------------------------------------------
# Arc tube helpers
# ---------------------------------------------------------------------------

def _build_arc_tube(radius, tube_r, tube_seg, y_offset, arc_segments=16):
    """Build a semicircular tube arc as a series of short cylinder segments.

    The arc spans 0 to pi (a half-circle / arch shape).  Each cylinder is
    placed at the corresponding point on the arc and rotated so its long axis
    is tangent to the circle.

    Args:
        radius:       Radius of the arc centre-line.
        tube_r:       Radius of the tube cross-section.
        tube_seg:     Number of vertices on the tube cross-section.
        y_offset:     Y position (depth offset in front of the panel).
        arc_segments: Number of cylinder segments forming the arc.

    Returns:
        List of Blender objects making up this arc.
    """
    all_parts = []
    seg_depth = math.pi * radius / arc_segments * 1.1  # slight overlap

    for i in range(arc_segments):
        # Angle sweeps from 0 (right) to pi (left) — classic rainbow arch
        angle = math.pi * i / (arc_segments - 1)

        cx = math.cos(angle) * radius   # X position along arc
        cz = math.sin(angle) * radius   # Z position along arc (height)

        # Tangent direction: perpendicular to radius vector, rotated +90 deg
        tang_angle = angle + math.pi / 2

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=tube_seg,
            radius=tube_r,
            depth=seg_depth,
            location=(cx, y_offset, cz),
        )
        seg_obj = bpy.context.active_object
        # Rotate around Y so the cylinder long axis aligns with the tangent
        seg_obj.rotation_euler = (0, tang_angle, 0)
        bpy.ops.object.transform_apply(rotation=True)
        all_parts.append(seg_obj)

    return all_parts


def _build_rainbow_arcs(cfg):
    """Build 7 concentric rainbow arc tubes and apply emission materials.

    Returns:
        List of all arc segment objects (one per stripe).
    """
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]
    tube_r = cfg["tube_radius"]
    tube_seg = cfg["tube_segments"]
    strength = cfg["glow_strength"]

    # The innermost arc must fit inside the sign height.
    # Use half the sign height as a base radius and space outward.
    arc_spacing = tube_r * 2.2
    num_arcs = len(RAINBOW_COLORS)

    # Inner-most arc radius; arcs grow outward from here.
    base_radius = h * 0.35

    # Y position: just in front of the panel face
    y_offset = d / 2 + tube_r * 0.5

    all_arc_objects = []

    for i, color in enumerate(RAINBOW_COLORS):
        arc_radius = base_radius + i * arc_spacing
        arc_parts = _build_arc_tube(
            radius=arc_radius,
            tube_r=tube_r,
            tube_seg=tube_seg,
            y_offset=y_offset,
            arc_segments=16,
        )

        # Join the segments of this arc into one object, then apply material
        arc_obj = _join(arc_parts, f"Arc_{COLOR_NAMES[i]}")
        _apply_emission_material(
            arc_obj, color, strength=strength,
            mat_name=f"Emit_{COLOR_NAMES[i]}",
        )
        all_arc_objects.append(arc_obj)

    return all_arc_objects


# ---------------------------------------------------------------------------
# Flat bars
# ---------------------------------------------------------------------------

def _build_flat_bars(cfg):
    """Build 7 horizontal emissive bars stacked vertically.

    Returns:
        List of bar objects.
    """
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]
    tube_r = cfg["tube_radius"]
    tube_seg = cfg["tube_segments"]
    strength = cfg["glow_strength"]

    num_bars = len(RAINBOW_COLORS)
    bar_spacing = h / (num_bars + 1)
    bar_length = w * 0.85
    y_offset = d / 2 + tube_r * 0.5

    bar_objects = []

    for i, color in enumerate(RAINBOW_COLORS):
        z = bar_spacing * (i + 1)  # evenly spaced from bottom

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=tube_seg,
            radius=tube_r,
            depth=bar_length,
            location=(0, y_offset, z),
            rotation=(0, math.radians(90), 0),
        )
        bar_obj = bpy.context.active_object
        bar_obj.name = f"Bar_{COLOR_NAMES[i]}"
        _apply_emission_material(
            bar_obj, color, strength=strength,
            mat_name=f"Emit_Bar_{COLOR_NAMES[i]}",
        )
        bar_objects.append(bar_obj)

    return bar_objects


# ---------------------------------------------------------------------------
# Word strip (simplified text placeholder)
# ---------------------------------------------------------------------------

def _build_word_strip(cfg):
    """Build a single wide emissive strip across the middle of the sign.

    Used as a simplified text/word placeholder for the 'word' variation.

    Returns:
        A single Blender object.
    """
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]
    tube_r = cfg["tube_radius"]
    tube_seg = cfg["tube_segments"]
    strength = cfg["glow_strength"]

    strip_length = w * 0.80
    y_offset = d / 2 + tube_r * 0.5
    z = h / 2  # vertically centered

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=tube_seg,
        radius=tube_r * 1.5,
        depth=strip_length,
        location=(0, y_offset, z),
        rotation=(0, math.radians(90), 0),
    )
    strip = bpy.context.active_object
    strip.name = "WordStrip"

    # Use a warm white for the word strip
    _apply_emission_material(
        strip,
        color=(1.0, 0.9, 0.6, 1.0),
        strength=strength,
        mat_name="Emit_WordStrip",
    )
    return strip


# ---------------------------------------------------------------------------
# Mounting brackets
# ---------------------------------------------------------------------------

def _build_brackets(cfg, style):
    """Build two small cylindrical mounting brackets on the rear of the panel.

    Returns:
        List of two bracket objects.
    """
    w = cfg["width"]
    h = cfg["height"]
    d = cfg["depth"]

    bracket_r = 0.015
    bracket_depth = 0.04
    y_pos = -(d / 2 + bracket_depth / 2)
    z_pos = h / 2  # vertically centered
    x_positions = [-w * 0.35, w * 0.35]

    brackets = []
    for idx, x in enumerate(x_positions):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8,
            radius=bracket_r,
            depth=bracket_depth,
            location=(x, y_pos, z_pos),
            rotation=(math.radians(90), 0, 0),
        )
        brk = bpy.context.active_object
        brk.name = f"Bracket_{idx}"
        _apply_material(
            brk, style, f"BracketMetal_{idx}",
            color=(0.4, 0.4, 0.4, 1.0),
            roughness=0.4,
            metallic=0.9,
        )
        brackets.append(brk)

    return brackets


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def create_led_rainbow_sign(cfg, style):
    """Create the full LED rainbow sign mesh.

    Args:
        cfg:   Configuration dict (see DEFAULT_CFG in __init__.py).
        style: AssetStyle instance controlling backing-panel material.

    Returns:
        The joined Blender object named 'LEDRainbowSign'.
    """
    _clear_scene()

    parts = []

    # 1. Backing panel
    panel = _build_panel(cfg, style)
    parts.append(panel)

    # 2. Emissive tubes (variation-dependent)
    variation = cfg.get("variation", "arch")
    if variation == "arch":
        arc_objs = _build_rainbow_arcs(cfg)
        parts.extend(arc_objs)
    elif variation == "flat_bars":
        bar_objs = _build_flat_bars(cfg)
        parts.extend(bar_objs)
    else:  # "word"
        strip = _build_word_strip(cfg)
        parts.append(strip)

    # 3. Mounting brackets
    brackets = _build_brackets(cfg, style)
    parts.extend(brackets)

    # Join all parts into a single mesh (materials are preserved per slot)
    result = _join(parts, "LEDRainbowSign")
    return _finalize(result, "LEDRainbowSign")
