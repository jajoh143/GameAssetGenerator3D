"""Flask server for the GameAssetGenerator3D character builder frontend."""

import os
import sys
import uuid
import subprocess
import threading
import shutil
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

# Load frontend/.env if present (defines BLENDER_PATH, PORT, etc.)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW_DIR = os.path.join(PROJECT_ROOT, "assets", "previews")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "assets")
os.makedirs(PREVIEW_DIR, exist_ok=True)

# ── Blender executable detection ──────────────────────────────────────────────
# Priority: BLENDER_PATH env var → common install locations → PATH fallback
_BLENDER_SEARCH = [
    # Linux
    "/usr/bin/blender",
    "/usr/local/bin/blender",
    "/snap/bin/blender",
    # macOS
    "/Applications/Blender.app/Contents/MacOS/Blender",
    # Windows (common)
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
]

def _find_blender():
    # 1. Explicit env var
    env_path = os.environ.get("BLENDER_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    # 2. shutil.which resolves from PATH (most reliable)
    which = shutil.which("blender")
    if which:
        return which
    # 3. Common install locations
    for path in _BLENDER_SEARCH:
        if os.path.isfile(path):
            return path
    return None

BLENDER_BIN = _find_blender()
if BLENDER_BIN:
    print(f"[app] Blender found: {BLENDER_BIN}")
else:
    print("[app] WARNING: Blender not found. Set BLENDER_PATH in frontend/.env")

app = Flask(__name__)

# Track running jobs: job_id -> {"status": str, "log": [str], "output": str|None}
_jobs = {}
_jobs_lock = threading.Lock()


def _blender_cmd(script_args, output_path):
    """Build the blender subprocess command."""
    exe = BLENDER_BIN or "blender"
    return [
        exe, "--background", "--python",
        os.path.join(PROJECT_ROOT, "scripts", "generate_humanoid.py"),
        "--", "--output", output_path,
    ] + script_args


def _run_job(job_id, cmd_or_callable):
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"

    log = []

    # Support both subprocess commands (list) and direct callables
    if callable(cmd_or_callable):
        try:
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cmd_or_callable()
            output = buf.getvalue()
            for line in output.splitlines():
                log.append(line)
                with _jobs_lock:
                    _jobs[job_id]["log"] = log[:]
            success = True
        except Exception as e:
            log.append(f"ERROR: {e}")
            import traceback
            log.append(traceback.format_exc())
            success = False
    else:
        cmd = cmd_or_callable
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, cwd=PROJECT_ROOT
            )
            for line in proc.stdout:
                line = line.rstrip()
                log.append(line)
                with _jobs_lock:
                    _jobs[job_id]["log"] = log[:]
            proc.wait()
            success = proc.returncode == 0
        except FileNotFoundError:
            log.append("ERROR: Blender executable not found.")
            log.append("Add 'blender' to your PATH or set BLENDER_PATH in frontend/.env")
            log.append(f"  e.g.  BLENDER_PATH=/path/to/blender")
            success = False
        except Exception as e:
            log.append(f"ERROR: {e}")
            success = False

    with _jobs_lock:
        _jobs[job_id]["status"] = "done" if success else "error"
        _jobs[job_id]["log"] = log


def _build_args(data):
    """Convert form data dict to CLI arg list."""
    args = []

    def _add(flag, key, default=None):
        val = data.get(key, default)
        if val and val != "none":
            args.extend([flag, str(val)])

    _add("--preset", "preset", "average")
    _add("--build", "build", "average")
    _add("--gender", "gender", "neutral")
    _add("--skin-tone", "skin_tone", "tan")
    _add("--hair-style", "hair_style", "short")

    hair_style = data.get("hair_style", "short")
    if hair_style and hair_style != "none":
        _add("--hair-color", "hair_color", "brown")

    _add("--lod", "lod", "mid")

    # Clothing: combine top + bottom
    top = data.get("clothing_top", "short_sleeve")
    bottom = data.get("clothing_bottom", "jeans")
    clothing_parts = [c for c in [top, bottom] if c and c != "none"]
    if clothing_parts:
        args.extend(["--clothing", ",".join(clothing_parts)])

    # Clothing color: per-item dict
    color_parts = []
    top_color = data.get("top_color")
    bottom_color = data.get("bottom_color")
    if top and top != "none" and top_color:
        color_parts.append(f"{top}:{top_color}")
    if bottom and bottom != "none" and bottom_color:
        color_parts.append(f"{bottom}:{bottom_color}")
    if color_parts:
        args.extend(["--clothing-color", ",".join(color_parts)])

    return args


@app.route("/")
def index():
    return render_template("index.html")


def _make_job_callable(data: dict, output_path: str, animations=None):
    """Build a callable that runs the pure-Python gltf_pipeline for a job."""
    import sys as _sys
    _sys.path.insert(0, PROJECT_ROOT)

    def _job():
        from generators.humanoid.presets import resolve_config
        from generators.humanoid.gltf_pipeline import build_humanoid_glb
        from generators.humanoid.hair import HAIR_COLORS

        def _parse_color(v):
            if v is None:
                return None
            if isinstance(v, (list, tuple)):
                return tuple(float(x) for x in v)
            if isinstance(v, str) and "," in v:
                parts = [float(x.strip()) for x in v.split(",")]
                if len(parts) == 3:
                    parts.append(1.0)
                return tuple(parts)
            return v  # named color string

        top = data.get("clothing_top", "short_sleeve")
        bottom = data.get("clothing_bottom", "jeans")
        clothing_list = [c for c in [top, bottom] if c and c != "none"]

        clothing_colors = {}
        top_color = data.get("top_color")
        bottom_color = data.get("bottom_color")
        if top and top != "none" and top_color:
            clothing_colors[top] = _parse_color(top_color) or top_color
        if bottom and bottom != "none" and bottom_color:
            clothing_colors[bottom] = _parse_color(bottom_color) or bottom_color

        anim_cfg = animations if animations is not None else []

        cfg = resolve_config(
            preset=data.get("preset", "average") or "average",
            build=data.get("build", "average") or "average",
            gender=data.get("gender", "neutral") or "neutral",
            skin_tone=_parse_color(data.get("skin_tone")) or "tan",
            hair_style=data.get("hair_style", "none") or "none",
            hair_color=_parse_color(data.get("hair_color")) or "brown",
            use_template=True,
            lod=data.get("lod", "mid") or "mid",
            overrides={
                "clothing": clothing_list,
                "clothing_color": clothing_colors if clothing_colors else None,
                "animations": anim_cfg,
            },
        )
        build_humanoid_glb(cfg, output_path)

    return _job


@app.route("/preview", methods=["POST"])
def preview():
    data = request.json or {}
    job_id = str(uuid.uuid4())
    preview_path = os.path.join(PREVIEW_DIR, f"{job_id}.glb")

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "log": [], "output": preview_path}

    job_fn = _make_job_callable(data, preview_path, animations=[])
    t = threading.Thread(target=_run_job, args=(job_id, job_fn), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json or {}
    job_id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, f"humanoid_{job_id[:8]}.glb")

    anims = data.get("animations", ["idle", "walk", "run", "jump", "attack"])
    if isinstance(anims, list) and len(anims) == 5:
        anim_cfg = "all"
    elif isinstance(anims, list) and anims:
        anim_cfg = anims
    else:
        anim_cfg = "all"

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "log": [], "output": output_path}

    job_fn = _make_job_callable(data, output_path, animations=anim_cfg)
    t = threading.Thread(target=_run_job, args=(job_id, job_fn), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/job/<job_id>")
def job_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    result = dict(job)
    if result["status"] == "done" and result.get("output"):
        result["download_url"] = f"/download/{job_id}"
    return jsonify(result)


@app.route("/model/<job_id>")
def serve_model(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or not job.get("output"):
        return "Not found", 404
    path = job["output"]
    if not os.path.exists(path):
        return "File not ready", 404
    return send_file(path, mimetype="model/gltf-binary")


@app.route("/download/<job_id>")
def download(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or not job.get("output"):
        return "Not found", 404
    path = job["output"]
    if not os.path.exists(path):
        return "File not ready", 404
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path),
                     mimetype="model/gltf-binary")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting character builder at http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
