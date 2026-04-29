"""Skeleton-fitting tests — no Blender required."""

from __future__ import annotations

import math

import pytest

from gag3d.rigging.skeleton import (
    SKELETON_TEMPLATE,
    bones_in_parent_order,
    fit_skeleton_from_bounds,
)


def test_template_is_well_formed():
    names = {b.name for b in SKELETON_TEMPLATE}
    for spec in SKELETON_TEMPLATE:
        if spec.parent is not None:
            assert spec.parent in names, f"{spec.name} references missing parent {spec.parent}"
    # Hips is the only root.
    roots = [b.name for b in SKELETON_TEMPLATE if b.parent is None]
    assert roots == ["Hips"]


def test_template_has_glb_humanoid_bones():
    names = {b.name for b in SKELETON_TEMPLATE}
    expected = {
        "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
        "Shoulder.L", "UpperArm.L", "LowerArm.L", "Hand.L",
        "Shoulder.R", "UpperArm.R", "LowerArm.R", "Hand.R",
        "UpperLeg.L", "LowerLeg.L", "Foot.L", "Toe.L",
        "UpperLeg.R", "LowerLeg.R", "Foot.R", "Toe.R",
    }
    assert expected.issubset(names)


def test_fit_centered_unit_human():
    # 1.8m tall, 0.5m wide, 0.3m deep, centered on origin, feet at Y=0.
    bounds = (-0.25, 0.25, 0.0, 1.8, -0.15, 0.15)
    skeleton = fit_skeleton_from_bounds(bounds)

    hips = skeleton.by_name("Hips")
    assert math.isclose(hips.head[1], 0.55 * 1.8, abs_tol=1e-6)
    assert math.isclose(hips.head[0], 0.0, abs_tol=1e-6)

    head = skeleton.by_name("Head")
    assert head.head[1] > hips.head[1]

    # Arm extends along +X for .L, -X for .R
    hand_l = skeleton.by_name("Hand.L")
    hand_r = skeleton.by_name("Hand.R")
    assert hand_l.head[0] > 0
    assert hand_r.head[0] < 0
    assert math.isclose(hand_l.head[0], -hand_r.head[0], abs_tol=1e-6)


def test_fit_rejects_zero_height():
    with pytest.raises(ValueError):
        fit_skeleton_from_bounds((0, 1, 5, 5, 0, 1))


def test_fit_handles_off_origin_mesh():
    # mesh shifted to +X+Z and resting on Y=10
    bounds = (10.0, 10.5, 10.0, 11.8, 5.0, 5.3)
    skeleton = fit_skeleton_from_bounds(bounds)
    hips = skeleton.by_name("Hips")
    assert math.isclose(hips.head[0], 10.25, abs_tol=1e-6)
    assert math.isclose(hips.head[1], 10.0 + 0.55 * 1.8, abs_tol=1e-6)
    assert math.isclose(hips.head[2], 5.15, abs_tol=1e-6)


def test_parent_order_iteration():
    skeleton = fit_skeleton_from_bounds((-0.25, 0.25, 0.0, 1.8, -0.15, 0.15))
    seen: set[str] = set()
    for bone in bones_in_parent_order(skeleton):
        if bone.parent is not None:
            assert bone.parent in seen, f"{bone.name} emitted before parent {bone.parent}"
        seen.add(bone.name)
    assert len(seen) == len(skeleton.bones)
