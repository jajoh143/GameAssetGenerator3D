"""Procedural keyframe animation cycles for the humanoid rig.

Each animation is a callable ``(arm_obj: bpy.types.Object) -> None`` that
adds a new ``Action`` and pushes it to an NLA strip on the armature so all
animations end up in the exported GLB.
"""

from __future__ import annotations

from .idle import idle
from .walk import walk
from .run import run
from .jump import jump
from .attack import attack

ANIMATIONS = {
    "idle": idle,
    "walk": walk,
    "run": run,
    "jump": jump,
    "attack": attack,
}

__all__ = ["ANIMATIONS", "idle", "walk", "run", "jump", "attack"]
