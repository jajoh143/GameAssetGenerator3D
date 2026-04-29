"""CLI parsing tests — no network, no Blender."""

from __future__ import annotations

import pytest

from gag3d.cli import _build_parser


def test_generate_requires_source():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["generate", "humanoid", "-o", "out.glb"])


def test_generate_rejects_both_sources():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["generate", "humanoid", "-o", "out.glb",
                           "--prompt", "x", "--image", "a.png"])


def test_generate_humanoid_prompt():
    parser = _build_parser()
    args = parser.parse_args([
        "generate", "humanoid",
        "-o", "out.glb",
        "--prompt", "a knight",
        "--animations", "idle,walk",
    ])
    assert args.asset_type == "humanoid"
    assert args.prompt == "a knight"
    assert args.animations == "idle,walk"


def test_generate_prop_image():
    parser = _build_parser()
    args = parser.parse_args([
        "generate", "prop",
        "-o", "chest.glb",
        "--image", "ref.png",
        "--resolution", "512",
    ])
    assert args.asset_type == "prop"
    assert str(args.image) == "ref.png"
    assert args.resolution == 512


def test_doctor_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["doctor"])
    assert args.command == "doctor"
