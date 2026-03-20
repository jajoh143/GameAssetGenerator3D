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
python -m generator generate humanoid -o assets/humanoid.glb

# List available asset types
python -m generator list
```

## Supported Assets

| Asset     | Script                      | Variations                              |
|-----------|-----------------------------|-----------------------------------------|
| Humanoid  | `generate_humanoid.py`      | Presets, builds, skin tones, hair       |
| Wall      | `generate_wall.py`          | Brick, concrete, corrugated + themes    |
| Floor     | `generate_floor.py`         | Tile, wood, stone + themes              |

## Humanoid Generator

The humanoid generator supports a layered configuration system for creating diverse characters:

```
preset → build modifier → hair → randomize → manual overrides
```

### Character Presets

| Preset    | Height | Description                                      |
|-----------|--------|--------------------------------------------------|
| `average` | 1.75m  | Standard proportions                             |
| `tall`    | 2.00m  | Long limbs, narrow hips                          |
| `short`   | 1.50m  | Compact, slightly thicker                        |
| `child`   | 1.20m  | Proportionally larger head, thin limbs           |
| `brute`   | 2.10m  | Wide shoulders, thick limbs, short neck          |
| `slender` | 1.85m  | Narrow frame, thin limbs, long neck              |

### Body Builds

Multiplier profiles applied on top of any preset:

| Build     | Effect                                           |
|-----------|--------------------------------------------------|
| `lean`    | Narrower shoulders/hips, thinner limbs           |
| `average` | No modification                                  |
| `stocky`  | Wider shoulders/hips, thicker limbs, shorter     |
| `heavy`   | Widest proportions, thickest limbs               |

### Skin Tones

**Natural:** `light`, `fair`, `medium`, `olive`, `tan`, `brown`, `dark`
**Fantasy:** `zombie`, `orc`, `frost`, `ember`, `shadow`

Custom RGBA values also supported (e.g., `0.5,0.4,0.3,1.0`).

### Hair Styles

| Style    | Description                                       |
|----------|---------------------------------------------------|
| `none`   | Bald (default)                                    |
| `buzzed` | Thin skullcap hugging the head                    |
| `short`  | Cap with volume on top and back coverage          |
| `spiky`  | Seven low-poly cones radiating from the crown     |
| `long`   | Side curtains and back flow past shoulders        |
| `mohawk` | Tall central ridge with shaved side caps          |

### Hair Colors

**Natural:** `black`, `dark_brown`, `brown`, `auburn`, `red`, `blonde`, `platinum`, `white`, `grey`
**Fantasy:** `blue`, `green`, `purple`, `pink`

Custom RGBA values also supported.

### Animations

Available animations: `idle`, `walk`, `run`, `jump`, `attack` (or `all`).

### Usage Examples

```bash
# Basic humanoid with default proportions
python -m generator generate humanoid -o assets/humanoid.glb

# Tall lean orc with spiky green hair
python -m generator generate humanoid -o assets/orc.glb \
    --preset tall --build lean --skin-tone orc \
    --hair-style spiky --hair-color green

# Stocky child zombie with mohawk
python -m generator generate humanoid -o assets/zombie_kid.glb \
    --preset child --build stocky --skin-tone zombie \
    --hair-style mohawk --hair-color purple

# Brute with custom proportions
python -m generator generate humanoid -o assets/tank.glb \
    --preset brute --shoulder-width 0.65 --limb-thickness 1.6

# Generate 10 unique crowd NPCs with seeded randomization
for i in $(seq 1 10); do
    python -m generator generate humanoid -o "assets/npc_$i.glb" \
        --preset average --hair-style short --randomize --seed $i
done

# Only idle and walk animations
python -m generator generate humanoid -o assets/guard.glb \
    --preset tall --animations idle,walk
```

### Direct Proportion Overrides

Any preset value can be overridden individually: `--height`, `--shoulder-width`, `--hip-width`, `--head-size`, `--arm-length`, `--leg-length`, `--torso-length`, `--limb-thickness`, `--torso-depth`.

## Wall & Floor Generators

Environment tiles with style theming:

```bash
# Fantasy stone wall with heavy wear
python -m generator generate wall -o assets/wall.glb \
    --variation stone --theme fantasy --wear 0.8

# Modern tile floor, pristine
python -m generator generate floor -o assets/floor.glb \
    --variation tile --theme modern --wear 0.1
```

**Themes:** `modern`, `fantasy`, `industrial`, `medieval`
**Materials:** `brick`, `concrete`, `metal`, `wood`, `stone`, `tile`
**Wear:** `0.0` (pristine) to `1.0` (heavily worn)

## Project Structure

```
GameAssetGenerator3D/
├── generator/              # CLI wrapper & shared utilities
│   ├── __main__.py         # CLI entry point
│   └── export.py           # Export helpers (glTF, FBX, etc.)
├── generators/             # Asset generators (run inside Blender)
│   ├── style.py            # Shared style/material system
│   ├── humanoid/
│   │   ├── __init__.py     # Main generate() entry point
│   │   ├── mesh.py         # Low-poly body mesh construction
│   │   ├── rig.py          # Armature & weight painting
│   │   ├── animation.py    # Walk, run, idle, jump, attack
│   │   ├── presets.py      # Character presets, builds, skin tones
│   │   └── hair.py         # Hair styles & colors
│   ├── wall/               # Wall tile generator
│   └── floor/              # Floor tile generator
├── scripts/                # Top-level Blender scripts
│   ├── generate_humanoid.py
│   ├── generate_wall.py
│   └── generate_floor.py
├── assets/                 # Generated output (gitignored)
└── tests/                  # Validation tests
```

## Running Tests

```bash
# All non-Blender tests
python -m pytest tests/

# Specific test file
python -m unittest tests/test_presets.py
```

## Extending

Each generator lives in `generators/<asset_type>/` and follows the pattern:

1. **mesh.py** — build geometry
2. **rig.py** — add armature and skin weights (if applicable)
3. **animation.py** — add animations (if applicable)

New generators can be added by creating a new directory with these modules and registering them in `generator/__main__.py`.

## License

MIT
