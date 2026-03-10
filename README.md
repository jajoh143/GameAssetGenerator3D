# GameAssetGenerator3D

A Blender-based procedural 3D game asset generator. Generate low-poly game-ready assets (meshes, rigs, animations) via Python scripts — no manual modeling required.

## Requirements

- [Blender](https://www.blender.org/) 3.6+ (must be on PATH, or set `BLENDER_PATH`)
- Python 3.10+ (for the CLI wrapper)

## Quick Start

Generate a rigged, animated low-poly humanoid:

```bash
# Using Blender directly
blender --background --python scripts/generate_humanoid.py -- --output assets/humanoid.glb

# Using the CLI wrapper
python -m generator generate humanoid --output assets/humanoid.glb
```

## Project Structure

```
GameAssetGenerator3D/
├── generator/              # CLI wrapper & shared utilities
│   ├── __init__.py
│   ├── __main__.py         # CLI entry point
│   └── export.py           # Export helpers (glTF, FBX, etc.)
├── generators/             # Asset generator scripts (run inside Blender)
│   └── humanoid/
│       ├── __init__.py
│       ├── mesh.py          # Low-poly body mesh construction
│       ├── rig.py           # Armature & weight painting
│       └── animation.py     # Walk cycle & basic animations
├── scripts/                # Top-level Blender scripts
│   └── generate_humanoid.py
├── assets/                 # Generated output (gitignored)
└── tests/                  # Validation tests
```

## Supported Assets

| Asset     | Status |
|-----------|--------|
| Humanoid  | v1     |

## Extending

Each generator lives in `generators/<asset_type>/` and follows the pattern:

1. **mesh.py** — build geometry
2. **rig.py** — add armature and skin weights
3. **animation.py** — add animations

New generators can be added by creating a new directory with these modules and registering them in `generator/__main__.py`.

## License

MIT
