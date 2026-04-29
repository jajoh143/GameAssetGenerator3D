"""In-memory job registry that runs pipeline jobs in worker threads.

Each job:
  * lives in ``<work_dir>/<job_id>/``
  * holds an event log so a late SSE subscriber can replay history
  * notifies async subscribers when new events arrive

Designed for a single-user local tool. Not durable across restarts.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gag3d.config import Config
from gag3d.pipeline import GenerationRequest, run as run_pipeline


@dataclass
class JobEvent:
    stage: str        # "queued" | "image" | "image_done" | "mesh" | "mesh_done" | "blender" | "done" | "error"
    message: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "message": self.message, "timestamp": self.timestamp}


@dataclass
class Job:
    id: str
    request: GenerationRequest
    job_dir: Path
    status: str = "queued"   # queued | running | done | error
    events: list[JobEvent] = field(default_factory=list)
    error: str | None = None
    output_glb: Path | None = None
    image_path: Path | None = None
    raw_mesh_glb: Path | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "asset_type": self.request.asset_type,
            "prompt": self.request.prompt,
            "image_supplied": self.request.image is not None,
            "animations": self.request.animations,
            "resolution": self.request.resolution,
            "events": [e.to_dict() for e in self.events],
            "error": self.error,
            "output_glb": str(self.output_glb) if self.output_glb else None,
            "image_path": str(self.image_path) if self.image_path else None,
            "raw_mesh_glb": str(self.raw_mesh_glb) if self.raw_mesh_glb else None,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    """Tracks jobs, dispatches them to a thread, fans events out to SSE clients."""

    def __init__(self, config: Config):
        self.config = config
        self._jobs: dict[str, Job] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = threading.Lock()

    # ─── Public API ──────────────────────────────────────────────────────

    def submit(self, request: GenerationRequest) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self.config.work_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Always write the final GLB inside the job dir for easy serving.
        request.output_glb = job_dir / "final.glb"

        job = Job(id=job_id, request=request, job_dir=job_dir)
        with self._lock:
            self._jobs[job_id] = job
            self._subscribers[job_id] = []

        self._emit(job, "queued", "Job queued.")
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        """Return a queue receiving every future event + the replay of past ones."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            for event in job.events:
                queue.put_nowait(event)
            self._subscribers[job_id].append(queue)
        # Stash loop on queue so the worker thread can post events back.
        queue._gag3d_loop = loop  # type: ignore[attr-defined]
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        with self._lock:
            subs = self._subscribers.get(job_id)
            if subs and queue in subs:
                subs.remove(queue)

    # ─── Internal ────────────────────────────────────────────────────────

    def _emit(self, job: Job, stage: str, message: str) -> None:
        event = JobEvent(stage=stage, message=message, timestamp=time.time())
        with self._lock:
            job.events.append(event)
            subs = list(self._subscribers.get(job.id, []))
        for q in subs:
            loop = getattr(q, "_gag3d_loop", None)
            if loop and loop.is_running():
                loop.call_soon_threadsafe(q.put_nowait, event)
            else:
                try:
                    q.put_nowait(event)
                except Exception:  # noqa: BLE001
                    pass

    def _run_job(self, job: Job) -> None:
        try:
            job.status = "running"
            self._emit(job, "running", "Worker started.")

            # Persist a request snapshot for the library view.
            (job.job_dir / "request.json").write_text(json.dumps({
                "asset_type": job.request.asset_type,
                "prompt": job.request.prompt,
                "animations": job.request.animations,
                "resolution": job.request.resolution,
                "normalize_height": job.request.normalize_height,
            }, indent=2))

            result = run_pipeline(
                job.request,
                self.config,
                progress=lambda stage, msg: self._emit(job, stage, msg),
            )
            job.output_glb = result.output_glb
            job.image_path = result.image_path
            job.raw_mesh_glb = result.raw_mesh_glb
            job.status = "done"
            job.finished_at = time.time()
            self._emit(job, "complete", "Job complete.")
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
            job.finished_at = time.time()
            tb = traceback.format_exc()
            self._emit(job, "error", f"{job.error}\n{tb}")
