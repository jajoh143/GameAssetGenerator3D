from pathlib import Path

from gag3d.config import Config


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("TRELLIS2_PATH", "/opt/TRELLIS.2")
    monkeypatch.setenv("TRELLIS2_PYTHON", "/opt/conda/envs/trellis2/bin/python")
    monkeypatch.setenv("BLENDER_PATH", "/usr/bin/blender")
    monkeypatch.setenv("GAG3D_WORK_DIR", "/tmp/gag3d")
    config = Config.from_env()
    assert config.openai_api_key == "sk-test"
    assert config.trellis2_path == Path("/opt/TRELLIS.2")
    assert config.trellis2_python == "/opt/conda/envs/trellis2/bin/python"
    assert config.blender_path == "/usr/bin/blender"
    assert config.work_dir == Path("/tmp/gag3d")


def test_config_defaults(monkeypatch):
    for k in ("OPENAI_API_KEY", "TRELLIS2_PATH", "TRELLIS2_PYTHON",
              "TRELLIS2_MODEL_ID", "BLENDER_PATH", "GAG3D_WORK_DIR"):
        monkeypatch.delenv(k, raising=False)
    config = Config.from_env()
    assert config.openai_api_key is None
    assert config.trellis2_path is None
    assert config.openai_image_model == "gpt-image-1"
    assert config.trellis2_model_id == "microsoft/TRELLIS.2-4B"
    assert config.blender_path == "blender"
