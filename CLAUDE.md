# CLAUDE.md — Project Guide for Claude Code

## Project Overview
GameAssetGenerator3D is a Blender-based procedural 3D game asset generator. It creates
game-ready assets (meshes, rigs, animations) via Python scripts that run inside Blender.

## Architecture
- `generators/` — Blender-internal Python modules for each asset type (mesh, rig, animation)
- `generator/` — CLI wrapper and export utilities (runs outside Blender, invokes it via subprocess)
- `scripts/` — Top-level Blender scripts that wire up generators + export (run via `blender --background --python`)
- `assets/` — Generated output directory (gitignored)
- `tests/` — Unit tests (non-Blender tests use standard Python, Blender tests need `blender --background`)

## Key Commands
- Generate humanoid: `blender --background --python scripts/generate_humanoid.py -- --output assets/humanoid.glb`
- CLI wrapper: `python -m generator generate humanoid -o assets/humanoid.glb`
- Run tests: `python -m pytest tests/`
- Run non-Blender tests only: `python -m unittest tests/test_humanoid_config.py`

## Adding New Asset Types
1. Create `generators/<asset_type>/` with `mesh.py`, `rig.py`, `animation.py`
2. Create `scripts/generate_<asset_type>.py`
3. Register in `generator/__main__.py` ASSET_SCRIPTS dict

## Conventions
- Bone names follow glTF/Mixamo convention (e.g., `UpperLeg.L`, `Hand.R`)
- All meshes are built at origin with feet at Z=0
- Default export format is GLB (glTF Binary)
- Low-poly target: 300-500 faces per asset for mobile/web compatibility
