"""Dance floor mesh construction — LED tile grid over a structural slab.

Coordinates:
    X  — width direction
    Y  — length direction
    Z  — up; slab bottom at Z=0, top at Z=depth
"""

import bpy
import bmesh
import math

from generators.base import BaseAssetGenerator
from generators.dance_floor import RAINBOW_PALETTE

# Bind base utilities as module-level names for brevity
_clear_scene = BaseAssetGenerator._clear_scene
_join = BaseAssetGenerator._join
_finalize = BaseAssetGenerator._finalize
_apply_material = BaseAssetGenerator._apply_material
_apply_emission_material = BaseAssetGenerator._apply_emission_material


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def create_dance_floor(cfg, style):
    """Build the full dance floor and return the joined Blender object."""
    _clear_scene()

    parts = []

    # 1. Structural slab (dark concrete / tile base)
    slab = _build_slab(cfg, style)
    parts.append(slab)

    # 2. LED tile grid
    variation = cfg.get("variation", "rainbow_grid")
    tiles = _build_tile_grid(cfg, variation)
    parts.extend(tiles)

    result = _join(parts, "DanceFloor")
    return _finalize(result, "DanceFloor")


# ---------------------------------------------------------------------------
# Slab
# ---------------------------------------------------------------------------

def _build_slab(cfg, style):
    """Plain rectangular slab — the structural base."""
    w = cfg["width"]
    l = cfg["length"]
    d = cfg["depth"]

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, d / 2))
    slab = bpy.context.active_object
    slab.scale = (w, l, d)
    bpy.ops.object.transform_apply(scale=True)
    slab.name = "DanceFloor_Slab"

    _apply_material(slab, style, "DanceFloor_Base",
                    color=(0.05, 0.05, 0.05, 1.0),
                    roughness=0.8, metallic=0.0)
    return slab


# ---------------------------------------------------------------------------
# LED tile grid
# ---------------------------------------------------------------------------

def _build_tile_grid(cfg, variation):
    """Build all LED tile panels and return list of objects."""
    w = cfg["width"]
    l = cfg["length"]
    d = cfg["depth"]
    ts = cfg["tile_size"]
    gap = cfg["tile_gap"]
    td = cfg["tile_depth"]
    strength = cfg["glow_strength"]

    step = ts + gap
    cols = int(w / step)
    rows = int(l / step)

    # Centre the grid
    x0 = -(cols * step - gap) / 2 + ts / 2
    y0 = -(rows * step - gap) / 2 + ts / 2
    z = d + td / 2  # sit on top of slab

    tiles = []
    for row in range(rows):
        for col in range(cols):
            x = x0 + col * step
            y = y0 + row * step
            color = _tile_color(col, row, cols, rows, variation)
            if color is None:
                continue  # unlit tile in checkerboard
            tile = _make_tile(x, y, z, ts, td, color, strength,
                              name=f"Tile_{col}_{row}")
            tiles.append(tile)

    return tiles


def _tile_color(col, row, cols, rows, variation):
    """Return RGBA for tile at (col, row), or None for an unlit tile."""
    if variation == "checkerboard":
        if (col + row) % 2 == 0:
            return (1.0, 1.0, 1.0, 1.0)   # bright white
        return None  # unlit — no emissive tile placed

    if variation == "rainbow_grid":
        # Cycle through palette based on diagonal position
        idx = (col + row) % len(RAINBOW_PALETTE)
        return RAINBOW_PALETTE[idx]

    if variation == "pulse_ring":
        # Distance from centre determines colour ring
        cx = cols / 2.0
        cy = rows / 2.0
        dist = math.sqrt((col - cx) ** 2 + (row - cy) ** 2)
        ring = int(dist) % len(RAINBOW_PALETTE)
        return RAINBOW_PALETTE[ring]

    # Fallback: white
    return (1.0, 1.0, 1.0, 1.0)


def _make_tile(x, y, z, size, depth, color, strength, name):
    """Create a single emissive LED tile panel."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    tile = bpy.context.active_object
    tile.scale = (size, size, depth)
    bpy.ops.object.transform_apply(scale=True)
    tile.name = name

    _apply_emission_material(tile, color, strength=strength,
                             mat_name=f"LED_{name}")
    return tile
