from gag3d.prompts import build_humanoid_prompt, build_prop_prompt


def test_humanoid_prompt_constraints():
    out = build_humanoid_prompt("a viking warrior")
    assert "viking warrior" in out
    assert "T-pose" in out
    assert "front" in out.lower()
    assert "white background" in out.lower()


def test_humanoid_prompt_custom_style():
    out = build_humanoid_prompt("a robot", style="cel-shaded toon")
    assert "cel-shaded toon" in out


def test_prop_prompt_basics():
    out = build_prop_prompt("a treasure chest")
    assert "treasure chest" in out
    assert "white background" in out.lower()
    assert "isolated" in out.lower()
