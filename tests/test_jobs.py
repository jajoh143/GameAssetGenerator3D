"""JobManager tests — patches gag3d.web.jobs.run_pipeline so we never call
the real TRELLIS.2 / Blender stack.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from gag3d.config import Config
from gag3d.pipeline import GenerationRequest, GenerationResult
from web import jobs as jobs_module
from web.jobs import JobManager


def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _make_config(tmp_path: Path) -> Config:
    return Config(
        openai_api_key="sk-test",
        openai_image_model="gpt-image-1",
        trellis2_path=tmp_path / "trellis2",
        trellis2_python="python",
        trellis2_model_id="microsoft/TRELLIS.2-4B",
        blender_path="blender",
        work_dir=tmp_path / "work",
    )


def test_successful_job_emits_full_event_chain(tmp_path, monkeypatch):
    config = _make_config(tmp_path)

    def fake_run(request, _config, progress=None):
        progress("image", "fake image")
        progress("image_done", "fake image done")
        progress("mesh", "fake mesh")
        progress("mesh_done", "fake mesh done")
        progress("blender", "fake blender")
        progress("done", "fake done")
        request.output_glb.parent.mkdir(parents=True, exist_ok=True)
        request.output_glb.write_bytes(b"fake glb")
        return GenerationResult(
            output_glb=request.output_glb,
            image_path=tmp_path / "fake_image.png",
            raw_mesh_glb=tmp_path / "fake_raw.glb",
        )

    monkeypatch.setattr(jobs_module, "run_pipeline", fake_run)

    manager = JobManager(config)
    job = manager.submit(GenerationRequest(
        asset_type="humanoid",
        output_glb=Path("placeholder"),
        prompt="a knight",
    ))

    assert _wait_until(lambda: job.status == "done"), f"job did not finish: {job.status}"
    stages = [e.stage for e in job.events]
    assert "queued" in stages
    assert "running" in stages
    assert "image" in stages
    assert "mesh" in stages
    assert "complete" in stages
    assert job.output_glb is not None
    assert job.output_glb.exists()


def test_job_records_pipeline_failure(tmp_path, monkeypatch):
    config = _make_config(tmp_path)

    def boom(request, _config, progress=None):
        progress("mesh", "starting")
        raise RuntimeError("fake TRELLIS crash")

    monkeypatch.setattr(jobs_module, "run_pipeline", boom)

    manager = JobManager(config)
    job = manager.submit(GenerationRequest(
        asset_type="humanoid",
        output_glb=Path("placeholder"),
        prompt="a knight",
    ))

    assert _wait_until(lambda: job.status == "error")
    assert job.error and "fake TRELLIS crash" in job.error
    assert any(e.stage == "error" for e in job.events)


def test_jobs_isolated_in_separate_dirs(tmp_path, monkeypatch):
    config = _make_config(tmp_path)

    def fake_run(request, _config, progress=None):
        request.output_glb.parent.mkdir(parents=True, exist_ok=True)
        request.output_glb.write_bytes(b"x")
        return GenerationResult(
            output_glb=request.output_glb,
            image_path=request.output_glb.parent / "input.png",
            raw_mesh_glb=request.output_glb.parent / "trellis.glb",
        )

    monkeypatch.setattr(jobs_module, "run_pipeline", fake_run)

    manager = JobManager(config)
    j1 = manager.submit(GenerationRequest(asset_type="prop", output_glb=Path("x"), prompt="a"))
    j2 = manager.submit(GenerationRequest(asset_type="prop", output_glb=Path("y"), prompt="b"))
    assert _wait_until(lambda: j1.status == "done" and j2.status == "done")
    assert j1.job_dir != j2.job_dir
    assert j1.output_glb.parent == j1.job_dir
    assert (j1.job_dir / "request.json").exists()


def test_list_jobs_newest_first(tmp_path, monkeypatch):
    config = _make_config(tmp_path)

    def fake_run(request, _config, progress=None):
        request.output_glb.parent.mkdir(parents=True, exist_ok=True)
        request.output_glb.write_bytes(b"x")
        return GenerationResult(
            output_glb=request.output_glb,
            image_path=tmp_path / "i.png",
            raw_mesh_glb=tmp_path / "r.glb",
        )

    monkeypatch.setattr(jobs_module, "run_pipeline", fake_run)

    manager = JobManager(config)
    j1 = manager.submit(GenerationRequest(asset_type="prop", output_glb=Path("x"), prompt="a"))
    time.sleep(0.01)
    j2 = manager.submit(GenerationRequest(asset_type="prop", output_glb=Path("y"), prompt="b"))
    assert _wait_until(lambda: j1.status == "done" and j2.status == "done")
    listing = manager.list_jobs()
    assert listing[0].id == j2.id
    assert listing[1].id == j1.id
