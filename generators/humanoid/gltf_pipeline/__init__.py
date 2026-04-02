"""gltf_pipeline: Blender-free humanoid GLB generator.

Builds a rigged, animated humanoid GLB using pygltflib and numpy,
without any bpy/bmesh/Blender dependency.

Public API:
    build_humanoid_glb(cfg, output_path) -> str
"""

from .builder import build_humanoid_gltf


def build_humanoid_glb(cfg: dict, output_path: str) -> str:
    """Build a rigged animated humanoid GLB without Blender.

    Args:
        cfg: Resolved character config dict (from presets.resolve_config).
        output_path: Path to write the .glb file.

    Returns:
        output_path (for chaining / confirmation).
    """
    import os
    gltf = build_humanoid_gltf(cfg)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    gltf.save(output_path)
    print(f"[gltf_pipeline] Saved {output_path}")
    return output_path
