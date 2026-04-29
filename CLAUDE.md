# CLAUDE.md — Project Guide for Claude Code

## Project Overview

GameAssetGenerator3D turns a **text prompt or reference image** into a
**rigged, animated, game-ready GLB** by chaining:

1. **OpenAI Images** (`gpt-image-1`) or a user-supplied PNG, then
2. **Microsoft TRELLIS.2-4B** (local, GPU) for image-to-3D, then
3. **Blender** (subprocess) for skeleton fitting, auto-weights, and
   animation baking.

Two asset types: **humanoid** (rig + animation cycles) and **prop**
(mesh only). Driven from CLI or a built-in FastAPI web UI with a
three.js viewer.

## Architecture

Four execution contexts — keep them separate:

| Context | What lives there | Why isolated |
| --- | --- | --- |
| Orchestrator (`gag3d/`) | Pipeline, CLI, OpenAI calls, subprocess plumbing | Plain Python; runs anywhere |
| Web frontend (`web/`) | FastAPI app, JobManager (worker thread), static SPA | Imports `gag3d` only |
| TRELLIS.2 conda env (`mesh_gen/trellis2_worker.py`) | Inference | flash-attn / nvdiffrast / CUDA 12.4 deps |
| Blender Python (`blender_jobs/rig_and_animate.py`) | Mesh import, rigging, weighting, animation, GLB export | Needs `bpy` and Blender's bundled Python |

The orchestrator never imports `bpy` or `trellis2`. It shells out.

## Pipeline progress

`gag3d.pipeline.run` accepts an optional `progress(stage, message)`
callback and emits these stages in order:

    image → image_done → mesh → mesh_done → blender → done

`web.jobs.JobManager` wraps that callback, broadcasts events to SSE
subscribers, and persists them on the `Job` so late subscribers see
history.

## Key Commands

```bash
# Set up env
cp .env.example .env && set -a && source .env && set +a

# Web UI (default 0.0.0.0:5000)
python -m gag3d serve

# CLI: end-to-end generate
python -m gag3d generate humanoid -o assets/output/knight.glb --prompt "a knight"
python -m gag3d generate prop     -o assets/output/chest.glb  --image my_chest.png

# Diagnose env
python -m gag3d doctor

# Tests (orchestrator + API; no Blender / GPU required)
python -m pytest tests/
```

## Web routes

| Method | Path | Purpose |
| --- | --- | --- |
| `GET`  | `/` | Static SPA |
| `GET`  | `/api/health` | Config status |
| `POST` | `/api/generate` | Multipart submit; returns `{job_id}` |
| `GET`  | `/api/jobs` | All jobs (newest first) |
| `GET`  | `/api/jobs/{id}` | Job state + replay log |
| `GET`  | `/api/jobs/{id}/events` | SSE progress stream |
| `GET`  | `/api/library` | Past generations |
| `GET`  | `/api/files/{id}/{name}` | Sandboxed file serving from `work_dir/<id>/` |

Each job lives in `<GAG3D_WORK_DIR>/<job_id>/` and always contains
`final.glb`. The library scans this dir.

## Adding a new animation

1. Create `gag3d/animation/<name>.py` exposing `def <name>(arm_obj): ...`.
2. Use helpers from `gag3d/animation/_common.py` (`keyframe_euler`,
   `keyframe_loc`, `new_action`, `push_to_nla`).
3. Register in `gag3d/animation/__init__.py`'s `ANIMATIONS` dict.
4. The CLI and web UI pick it up automatically (web UI: add a checkbox
   in `web/static/index.html` if you want it surfaced by default).

## Adding a new asset type

1. Add a prompt builder in `gag3d/prompts/<asset>.py`.
2. Add a `run_<asset>` function in `blender_jobs/rig_and_animate.py`
   and dispatch it from `main()`.
3. Add `<asset>` to the CLI's `asset_type` choices, the web form's
   select, and `pipeline.run`'s asset-type branch.

## Conventions

- Bone names follow glTF/Mixamo (`UpperLeg.L`, `Hand.R`, `Spine2`).
- Mesh is normalized to feet-on-floor (Z=0 in Blender / Y=0 in glTF).
- Default humanoid height: 1.8 m. Default prop height: 1.0 m.
- TRELLIS.2 outputs are Y-up, facing −Z. The Blender importer remaps to
  Z-up; the skeleton fitter's "Y-up bounds" are constructed by swapping
  Y↔Z when reading Blender bbox values.
- Animations are stashed on NLA tracks before export so they all ship
  inside the GLB.

## Things to avoid

- Don't import `bpy` or `trellis2` from the orchestrator package or `web/`.
- Don't add fallbacks for missing TRELLIS.2 — local-GPU-only by design.
  Add a new `MeshGenerator` subclass when a hosted-API path is needed.
- Don't add auth / multi-user features without deciding on a real
  threat model first; current default is `0.0.0.0:5000` no-auth, single
  user.
- Don't hand-edit GLBs after export.
