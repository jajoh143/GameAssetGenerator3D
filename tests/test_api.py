"""FastAPI route tests using TestClient — pipeline is monkey-patched."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gag3d.config import Config
from gag3d.pipeline import GenerationResult
from web import jobs as jobs_module
from web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    config = Config(
        openai_api_key="sk-test",
        openai_image_model="gpt-image-1",
        trellis2_path=tmp_path / "trellis2",
        trellis2_python="python",
        trellis2_model_id="microsoft/TRELLIS.2-4B",
        blender_path="blender",
        work_dir=tmp_path / "work",
    )

    def fake_run(request, _config, progress=None):
        if progress:
            progress("image", "fake image")
            progress("done", "fake done")
        request.output_glb.parent.mkdir(parents=True, exist_ok=True)
        request.output_glb.write_bytes(b"GLB-FAKE")
        return GenerationResult(
            output_glb=request.output_glb,
            image_path=request.output_glb.parent / "input.png",
            raw_mesh_glb=request.output_glb.parent / "trellis.glb",
        )

    monkeypatch.setattr(jobs_module, "run_pipeline", fake_run)
    app = create_app(config)
    with TestClient(app) as c:
        yield c, config


def _wait_done(client, job_id, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{job_id}").json()
        if r["status"] in ("done", "error"):
            return r
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


def test_health_reports_config(client):
    c, _config = client
    h = c.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["openai_configured"] is True
    assert h["trellis2_configured"] is True


def test_index_served(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "GameAssetGenerator3D" in r.text


def test_generate_requires_prompt_or_image(client):
    c, _ = client
    r = c.post("/api/generate", data={"asset_type": "humanoid"})
    assert r.status_code == 400


def test_generate_rejects_unknown_asset_type(client):
    c, _ = client
    r = c.post("/api/generate", data={"asset_type": "elf", "prompt": "x"})
    assert r.status_code == 400


def test_generate_full_flow(client):
    c, config = client
    r = c.post("/api/generate", data={
        "asset_type": "humanoid",
        "prompt": "a robot",
        "resolution": 512,
        "height": 1.7,
        "animations": "idle,walk",
    })
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    final = _wait_done(c, job_id)
    assert final["status"] == "done"
    assert final["output_glb"].endswith("/final.glb")

    listing = c.get("/api/jobs").json()
    assert any(j["id"] == job_id for j in listing["jobs"])

    library = c.get("/api/library").json()
    assert any(item["id"] == job_id for item in library["items"])

    # Serve the GLB file.
    r = c.get(f"/api/files/{job_id}/final.glb")
    assert r.status_code == 200
    assert r.content == b"GLB-FAKE"


def test_file_serving_blocks_traversal(client):
    c, _ = client
    r = c.get("/api/files/..%2F..%2Fetc/passwd")
    assert r.status_code in (400, 404)


def test_unknown_job_returns_404(client):
    c, _ = client
    assert c.get("/api/jobs/doesnotexist").status_code == 404
    assert c.get("/api/jobs/doesnotexist/events").status_code == 404
