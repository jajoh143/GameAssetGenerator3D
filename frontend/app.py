"""Flask server for the GameAssetGenerator3D character builder frontend."""

import os
import sys
import uuid
import subprocess
import threading
from flask import Flask, render_template, request, jsonify, send_file

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW_DIR = os.path.join(PROJECT_ROOT, "assets", "previews")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "assets")
os.makedirs(PREVIEW_DIR, exist_ok=True)

app = Flask(__name__)

# Track running jobs: job_id -> {"status": str, "log": [str], "output": str|None}
_jobs = {}
_jobs_lock = threading.Lock()


def _blender_cmd(script_args, output_path):
    """Build the blender subprocess command."""
    return [
        "blender", "--background", "--python",
        os.path.join(PROJECT_ROOT, "scripts", "generate_humanoid.py"),
        "--", "--output", output_path,
    ] + script_args


def _run_job(job_id, cmd):
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"

    log = []
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


@app.route("/preview", methods=["POST"])
def preview():
    data = request.json or {}
    job_id = str(uuid.uuid4())
    preview_path = os.path.join(PREVIEW_DIR, f"{job_id}.glb")

    args = _build_args(data)
    args.extend(["--animations", "none"])  # skip animations for fast preview

    cmd = _blender_cmd(args, preview_path)

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "log": [], "output": preview_path}

    t = threading.Thread(target=_run_job, args=(job_id, cmd), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json or {}
    job_id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, f"humanoid_{job_id[:8]}.glb")

    args = _build_args(data)
    anims = data.get("animations", ["idle", "walk", "run", "jump", "attack"])
    if isinstance(anims, list) and len(anims) == 5:
        args.extend(["--animations", "all"])
    elif isinstance(anims, list) and anims:
        args.extend(["--animations", ",".join(anims)])

    cmd = _blender_cmd(args, output_path)

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "log": [], "output": output_path}

    t = threading.Thread(target=_run_job, args=(job_id, cmd), daemon=True)
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
