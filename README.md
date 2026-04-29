# GameAssetGenerator3D

Pipeline that turns a **text prompt or reference image** into a **rigged,
animated, game-ready GLB**:

```
prompt ──► OpenAI Images ──► PNG ──► TRELLIS.2 ──► static GLB ──► Blender ──► rigged + animated GLB
                                  ▲
                                  │
       --image my_concept.png ────┘
```

- **Image** — `gpt-image-1` (OpenAI Images) or a file you supply.
- **Mesh** — Microsoft [TRELLIS.2-4B](https://github.com/microsoft/TRELLIS.2)
  running locally on your GPU box (4B params, PBR materials, ≥24 GB VRAM).
- **Rig + animation** — pure-Python Blender job that fits a humanoid
  skeleton onto the mesh, applies heat-diffusion auto-weights, and bakes
  idle / walk / run / jump / attack cycles into NLA tracks of the exported
  GLB. Props skip the rig step.

## Requirements

- Linux box with NVIDIA GPU (≥24 GB VRAM), CUDA 12.4
- Python 3.10+
- Blender 3.6+ on `PATH` (or set `BLENDER_PATH`)
- A TRELLIS.2 checkout + conda env (instructions below)
- An OpenAI API key (only required if you use `--prompt`)

## Install

```bash
# 1. Orchestrator deps
pip install -r requirements.txt

# 2. TRELLIS.2 (one-time, in its own conda env)
git clone -b main --recursive https://github.com/microsoft/TRELLIS.2.git /opt/TRELLIS.2
cd /opt/TRELLIS.2
. ./setup.sh --new-env --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm

# 3. Tell gag3d where everything lives
cp .env.example .env
# edit .env — fill in OPENAI_API_KEY, TRELLIS2_PATH, TRELLIS2_PYTHON, BLENDER_PATH
set -a; source .env; set +a

# 4. Verify
python -m gag3d doctor
```

## Quick Start

### Web frontend (recommended)

```bash
python -m gag3d serve              # http://<gpu-box>:5000
```

Three tabs:
- **Generate** — pick humanoid/prop, prompt or upload image, choose animations,
  hit Generate. Live SSE progress log streams stage transitions
  (`image → mesh → blender → done`).
- **Preview** — three.js viewer with orbit camera, animation dropdown,
  play/pause/speed slider, and a skeleton overlay toggle for inspecting the
  fitted rig.
- **Library** — every past generation in `GAG3D_WORK_DIR`, click a card to
  open it in Preview.

Defaults: bind on `0.0.0.0:5000`, no auth (single-user LAN tool).
Override with `--host 127.0.0.1` for local-only.

### CLI

```bash
# Prompt → rigged humanoid with all animations
python -m gag3d generate humanoid \
    -o assets/output/knight.glb \
    --prompt "a cel-shaded medieval knight in plate armor"

# Existing concept image → rigged humanoid with only idle and walk
python -m gag3d generate humanoid \
    -o assets/output/wizard.glb \
    --image my_wizard_concept.png \
    --animations idle,walk

# Static prop, lower TRELLIS resolution for speed
python -m gag3d generate prop \
    -o assets/output/chest.glb \
    --prompt "a wooden treasure chest with iron bands" \
    --resolution 512
```

## Pipeline detail

1. **Image stage.** Either reads `--image` straight through, or sends a
   constrained T-pose / isolated-object prompt to `gpt-image-1` and saves
   the PNG to the work dir.
2. **Mesh stage.** Spawns a subprocess that runs
   `gag3d/mesh_gen/trellis2_worker.py` inside the TRELLIS.2 conda env. The
   worker loads `Trellis2ImageTo3DPipeline.from_pretrained(...)`, runs
   inference at the requested voxel resolution (512 / 1024 / 1536), and
   exports a textured GLB with PBR materials.
3. **Blender stage.** Spawns `blender --background --python
   gag3d/blender_jobs/rig_and_animate.py -- <job.json>`:
   - imports the TRELLIS GLB,
   - normalizes it to a target height (1.8 m for humanoids by default),
   - for humanoids: fits the bone template in
     `gag3d/rigging/skeleton.py` to the mesh's bounding box, builds an
     armature with glTF/Mixamo bone names, and binds with
     `parent_set(type="ARMATURE_AUTO")` (heat-diffusion weights),
   - for each requested animation, calls a keyframe builder from
     `gag3d/animation/` and pushes the action onto an NLA track,
   - re-exports as GLB.

## Rigging assumptions

The skeleton fitter expects:
- **Y-up, facing −Z** in the source GLB (TRELLIS.2's default).
- **Roughly symmetric, T-pose stance.** The default OpenAI prompt template
  asks for a strict T-pose; if you supply your own image, give the
  generator a clean front-facing T-pose to match.

Vitruvian-derived ratios place the skeleton inside the mesh's bounding
box. This is intentionally simple — see "Roadmap" below for the upgrade
path.

## CLI reference

```
python -m gag3d generate <humanoid|prop> -o OUTPUT.glb
    (--prompt TEXT | --image PATH)
    [--style "..."]
    [--animations idle,walk,run,jump,attack]
    [--resolution 512|1024|1536]
    [--height METERS]
    [--keep-intermediates]

python -m gag3d serve [--host 0.0.0.0] [--port 5000] [--reload]
python -m gag3d doctor
```

## Web API

The web frontend talks to a small JSON+SSE API you can also drive yourself:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET`  | `/api/health` | Config status (OpenAI/TRELLIS configured?) |
| `POST` | `/api/generate` | Multipart form: `asset_type`, `prompt`, `image`, `animations`, `resolution`, `height`. Returns `{job_id}`. |
| `GET`  | `/api/jobs` | All jobs (newest first) |
| `GET`  | `/api/jobs/{id}` | Job state + event log |
| `GET`  | `/api/jobs/{id}/events` | Server-Sent Events stream of progress |
| `GET`  | `/api/library` | Past generations (anything in `GAG3D_WORK_DIR/<id>/final.glb`) |
| `GET`  | `/api/files/{id}/{name}` | Serve files from a job dir (sandboxed) |

## Project layout

```
gag3d/                       # orchestrator package (no bpy, no CUDA deps)
├── __main__.py              # python -m gag3d
├── cli.py                   # argparse front-end
├── pipeline.py              # orchestrator (emits stage progress)
├── config.py                # env-var driven Config
├── image_gen/               # OpenAI Images + file-source adapters
├── mesh_gen/
│   ├── trellis2.py          # subprocess wrapper
│   └── trellis2_worker.py   # runs inside TRELLIS.2 conda env
├── prompts/                 # prompt templates (T-pose, isolated prop)
├── rigging/
│   └── skeleton.py          # bone template + bbox fitting (no bpy)
├── animation/
│   ├── idle.py walk.py run.py jump.py attack.py
│   └── _common.py           # keyframe helpers (Blender-only)
└── blender_jobs/
    └── rig_and_animate.py   # the Blender-side script

web/                         # FastAPI frontend
├── app.py                   # routes: generate, jobs, library, files
├── jobs.py                  # in-memory JobManager + SSE fanout
└── static/
    ├── index.html           # SPA shell with three tabs
    ├── app.js               # three.js viewer + EventSource progress
    └── style.css

tests/                       # non-Blender unit + API tests (pytest)
assets/
├── output/                  # GAG3D_WORK_DIR — job folders live here
├── ExampleCharacters/       # reference rigged GLBs (kept from older rev)
└── TemplateMeshes/          # reference low-poly templates
```

## Tests

```bash
pip install -r requirements.txt
python -m pytest tests/
```

The skeleton fitter, prompt templates, CLI, and config layer are covered
without bpy. The Blender-side code is exercised end-to-end by running the
pipeline against real input.

## Roadmap

- [ ] Replace bbox-only skeleton fit with 2D pose estimation
      (MediaPipe / RTMPose) on the source image, projected onto the mesh.
- [ ] Quadruped + creature rig templates.
- [ ] Optional Mixamo/AccuRIG hand-off for higher-fidelity binding.
- [ ] Hosted-API mesh adapter (Replicate / fal) as a fallback for
      machines without a local GPU.

## License

MIT
