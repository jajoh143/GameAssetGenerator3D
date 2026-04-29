"""Humanoid skeleton template + landmark-based fitting.

Bone names follow the glTF/Mixamo convention (e.g. ``UpperLeg.L``,
``Hand.R``) so exported rigs can be retargeted with standard tooling.

Landmark fitting uses Vitruvian-derived ratios applied to the mesh bounding
box. We assume the mesh:
  * is Y-up
  * faces -Z (i.e. the camera looked down -Z when TRELLIS reconstructed it)
  * is in a roughly symmetric T-pose

When those assumptions hold, this is enough to place a usable skeleton. The
returned positions are then used inside Blender to construct an armature.
Pure data — no Blender imports — so this module is unit-testable without bpy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


# (fraction_of_height, side_factor) where side_factor multiplies half-shoulder-width
# along +X for .L and -X for .R bones.
@dataclass(frozen=True)
class BoneSpec:
    name: str
    parent: str | None
    head_y_frac: float        # vertical position as fraction of mesh height
    head_x_frac: float        # horizontal position as fraction of half-shoulder-width
    head_z_frac: float        # depth as fraction of mesh depth (signed: + = forward)
    tail_offset: tuple[float, float, float]  # (dx, dy, dz) in fractions of height


SKELETON_TEMPLATE: tuple[BoneSpec, ...] = (
    # Root + spine
    BoneSpec("Hips",     None,         0.55, 0.0, 0.0, (0.0,  0.07, 0.0)),
    BoneSpec("Spine",    "Hips",       0.62, 0.0, 0.0, (0.0,  0.07, 0.0)),
    BoneSpec("Spine1",   "Spine",      0.69, 0.0, 0.0, (0.0,  0.06, 0.0)),
    BoneSpec("Spine2",   "Spine1",     0.75, 0.0, 0.0, (0.0,  0.07, 0.0)),
    BoneSpec("Neck",     "Spine2",     0.84, 0.0, 0.0, (0.0,  0.04, 0.0)),
    BoneSpec("Head",     "Neck",       0.88, 0.0, 0.0, (0.0,  0.10, 0.0)),

    # Left arm — extended along +X in T-pose
    BoneSpec("Shoulder.L",  "Spine2",      0.83,  0.40, 0.0, ( 0.06, 0.0, 0.0)),
    BoneSpec("UpperArm.L",  "Shoulder.L",  0.83,  1.00, 0.0, ( 0.20, 0.0, 0.0)),
    BoneSpec("LowerArm.L",  "UpperArm.L",  0.83,  2.00, 0.0, ( 0.18, 0.0, 0.0)),
    BoneSpec("Hand.L",      "LowerArm.L",  0.83,  2.95, 0.0, ( 0.08, 0.0, 0.0)),

    # Right arm — extended along -X
    BoneSpec("Shoulder.R",  "Spine2",      0.83, -0.40, 0.0, (-0.06, 0.0, 0.0)),
    BoneSpec("UpperArm.R",  "Shoulder.R",  0.83, -1.00, 0.0, (-0.20, 0.0, 0.0)),
    BoneSpec("LowerArm.R",  "UpperArm.R",  0.83, -2.00, 0.0, (-0.18, 0.0, 0.0)),
    BoneSpec("Hand.R",      "LowerArm.R",  0.83, -2.95, 0.0, (-0.08, 0.0, 0.0)),

    # Left leg
    BoneSpec("UpperLeg.L",  "Hips",        0.53,  0.45, 0.0, (0.0, -0.27, 0.0)),
    BoneSpec("LowerLeg.L",  "UpperLeg.L",  0.27,  0.45, 0.0, (0.0, -0.24, 0.0)),
    BoneSpec("Foot.L",      "LowerLeg.L",  0.03,  0.45, 0.0, (0.0,  0.0,  0.10)),
    BoneSpec("Toe.L",       "Foot.L",      0.03,  0.45, 0.10, (0.0, 0.0, 0.04)),

    # Right leg
    BoneSpec("UpperLeg.R",  "Hips",        0.53, -0.45, 0.0, (0.0, -0.27, 0.0)),
    BoneSpec("LowerLeg.R",  "UpperLeg.R",  0.27, -0.45, 0.0, (0.0, -0.24, 0.0)),
    BoneSpec("Foot.R",      "LowerLeg.R",  0.03, -0.45, 0.0, (0.0,  0.0,  0.10)),
    BoneSpec("Toe.R",       "Foot.R",      0.03, -0.45, 0.10, (0.0, 0.0, 0.04)),
)


@dataclass
class FittedBone:
    name: str
    parent: str | None
    head: tuple[float, float, float]
    tail: tuple[float, float, float]


@dataclass
class HumanoidSkeleton:
    bones: list[FittedBone] = field(default_factory=list)

    def by_name(self, name: str) -> FittedBone:
        for b in self.bones:
            if b.name == name:
                return b
        raise KeyError(name)


def fit_skeleton_from_bounds(
    bounds: Sequence[float],
    half_shoulder_width: float | None = None,
) -> HumanoidSkeleton:
    """Place the humanoid template inside the given mesh bounding box.

    bounds: (xmin, xmax, ymin, ymax, zmin, zmax)
    half_shoulder_width: half the distance between left and right shoulders, in
        world units. If None, derived as 22% of mesh height (Vitruvian-ish).
    """
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    height = ymax - ymin
    depth = zmax - zmin
    cx = (xmin + xmax) / 2.0
    cz = (zmin + zmax) / 2.0

    if height <= 0:
        raise ValueError("Mesh has zero or negative height; cannot fit skeleton.")

    if half_shoulder_width is None:
        half_shoulder_width = 0.11 * height  # shoulder span ≈ 22% of height

    fitted: list[FittedBone] = []
    for spec in SKELETON_TEMPLATE:
        head_x = cx + spec.head_x_frac * half_shoulder_width
        head_y = ymin + spec.head_y_frac * height
        head_z = cz + spec.head_z_frac * depth

        dx, dy, dz = spec.tail_offset
        tail_x = head_x + dx * height * (1.0 if spec.head_x_frac >= 0 else 1.0)
        tail_y = head_y + dy * height
        tail_z = head_z + dz * height

        fitted.append(
            FittedBone(
                name=spec.name,
                parent=spec.parent,
                head=(head_x, head_y, head_z),
                tail=(tail_x, tail_y, tail_z),
            )
        )

    return HumanoidSkeleton(bones=fitted)


def bones_in_parent_order(skeleton: HumanoidSkeleton) -> Iterable[FittedBone]:
    """Yield bones such that every bone is preceded by its parent."""
    by_name = {b.name: b for b in skeleton.bones}
    emitted: set[str] = set()

    def emit(b: FittedBone):
        if b.parent and b.parent not in emitted:
            emit(by_name[b.parent])
        if b.name not in emitted:
            emitted.add(b.name)
            yield b

    out: list[FittedBone] = []
    for b in skeleton.bones:
        out.extend(emit(b))
    return out
