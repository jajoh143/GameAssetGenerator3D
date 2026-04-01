"""glTF PBR material builders for the humanoid gltf_pipeline."""

from pygltflib import Material, PbrMetallicRoughness


def skin_material(rgba: tuple) -> Material:
    """Build a skin PBR material.

    Args:
        rgba: (r, g, b, a) base color factors, each 0.0–1.0.

    Returns:
        pygltflib Material object.
    """
    r, g, b, a = rgba
    return Material(
        name="Skin",
        pbrMetallicRoughness=PbrMetallicRoughness(
            baseColorFactor=[r, g, b, a],
            roughnessFactor=0.42,
            metallicFactor=0.0,
        ),
        doubleSided=False,
    )


def hair_material(rgba: tuple) -> Material:
    """Build a hair PBR material.

    Args:
        rgba: (r, g, b, a) base color factors.

    Returns:
        pygltflib Material object.
    """
    r, g, b, a = rgba
    return Material(
        name="Hair",
        pbrMetallicRoughness=PbrMetallicRoughness(
            baseColorFactor=[r, g, b, a],
            roughnessFactor=0.60,
            metallicFactor=0.0,
        ),
        doubleSided=True,
    )


def clothing_material(ctype: str, rgba: tuple) -> Material:
    """Build a clothing PBR material.

    Args:
        ctype: Clothing type name (used as material name).
        rgba: (r, g, b, a) base color factors.

    Returns:
        pygltflib Material object.
    """
    r, g, b, a = rgba
    return Material(
        name=f"Clothing_{ctype}",
        pbrMetallicRoughness=PbrMetallicRoughness(
            baseColorFactor=[r, g, b, a],
            roughnessFactor=0.65,
            metallicFactor=0.0,
        ),
        doubleSided=False,
    )
