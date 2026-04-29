"""FastAPI app — generation, progress streaming, library, file serving."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from gag3d.config import Config
from gag3d.pipeline import GenerationRequest

from .jobs import JobManager

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()
    config.work_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="GameAssetGenerator3D")
    manager = JobManager(config)
    app.state.manager = manager
    app.state.config = config

    # ─── Static frontend ─────────────────────────────────────────────────
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse((STATIC_DIR / "index.html").read_text())

    # ─── Health / config ─────────────────────────────────────────────────

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "openai_configured": bool(config.openai_api_key),
            "trellis2_configured": config.trellis2_path is not None,
            "blender": config.blender_path,
            "work_dir": str(config.work_dir),
        }

    # ─── Job creation ────────────────────────────────────────────────────

    @app.post("/api/generate")
    async def generate(
        asset_type: str = Form(...),
        prompt: str | None = Form(None),
        style: str | None = Form(None),
        animations: str | None = Form(None),
        resolution: int = Form(1024),
        height: float = Form(1.8),
        image: UploadFile | None = File(None),
    ) -> dict:
        if asset_type not in ("humanoid", "prop"):
            raise HTTPException(400, f"Unknown asset_type: {asset_type}")
        if not prompt and image is None:
            raise HTTPException(400, "Either prompt or image is required.")

        anim_list = None
        if animations:
            anim_list = [a.strip() for a in animations.split(",") if a.strip()]

        # Stage uploaded image into work_dir before we know the job id.
        uploaded_path: Path | None = None
        if image is not None:
            staging = config.work_dir / "_uploads"
            staging.mkdir(parents=True, exist_ok=True)
            uploaded_path = staging / f"{image.filename}"
            with uploaded_path.open("wb") as f:
                shutil.copyfileobj(image.file, f)

        request = GenerationRequest(
            asset_type=asset_type,
            output_glb=Path("placeholder"),  # JobManager.submit overrides this
            prompt=prompt,
            image=uploaded_path,
            style=style,
            animations=anim_list,
            resolution=resolution,
            normalize_height=height,
        )

        job = manager.submit(request)
        return {"job_id": job.id}

    # ─── Job status / events ─────────────────────────────────────────────

    @app.get("/api/jobs")
    def list_jobs() -> dict:
        return {"jobs": [j.to_dict() for j in manager.list_jobs()]}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(404, f"Unknown job: {job_id}")
        return job.to_dict()

    @app.get("/api/jobs/{job_id}/events")
    async def stream_events(job_id: str):
        try:
            queue = await manager.subscribe(job_id)
        except KeyError:
            raise HTTPException(404, f"Unknown job: {job_id}")

        async def event_gen():
            try:
                while True:
                    event = await queue.get()
                    payload = json.dumps(event.to_dict())
                    yield f"data: {payload}\n\n"
                    if event.stage in ("complete", "error"):
                        break
            finally:
                manager.unsubscribe(job_id, queue)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # ─── Library ─────────────────────────────────────────────────────────

    @app.get("/api/library")
    def library() -> dict:
        items = []
        if config.work_dir.exists():
            for sub in sorted(config.work_dir.iterdir(), reverse=True):
                final = sub / "final.glb"
                if not final.exists():
                    continue
                meta_path = sub / "request.json"
                meta = {}
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                    except json.JSONDecodeError:
                        pass
                items.append({
                    "id": sub.name,
                    "glb_url": f"/api/files/{sub.name}/final.glb",
                    "image_url": _first_image_url(sub),
                    "meta": meta,
                    "modified": final.stat().st_mtime,
                })
        return {"items": items}

    def _first_image_url(job_dir: Path) -> str | None:
        for name in ("input.png", "final_input.png"):
            if (job_dir / name).exists():
                return f"/api/files/{job_dir.name}/{name}"
        for png in job_dir.glob("*.png"):
            return f"/api/files/{job_dir.name}/{png.name}"
        return None

    # ─── File serving (sandboxed to work_dir) ────────────────────────────

    @app.get("/api/files/{job_id}/{name}")
    def serve_file(job_id: str, name: str) -> FileResponse:
        # Reject any path traversal attempts.
        if "/" in job_id or ".." in job_id or "/" in name or ".." in name:
            raise HTTPException(400, "Invalid path")
        target = (config.work_dir / job_id / name).resolve()
        try:
            target.relative_to(config.work_dir.resolve())
        except ValueError:
            raise HTTPException(400, "Invalid path")
        if not target.exists() or not target.is_file():
            raise HTTPException(404, f"Not found: {job_id}/{name}")
        return FileResponse(target)

    return app


# Module-level app for `uvicorn web.app:app`.
app = create_app()
