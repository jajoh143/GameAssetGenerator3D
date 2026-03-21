"""Base class for all asset generators.

Provides a common OOP interface so generators can inherit shared utilities
and override only what they need. Every generator subclass should:

  1. Define DEFAULT_CFG with asset-specific parameters
  2. Override generate() to return the Blender object
  3. Optionally override _default_style() for a custom default AssetStyle

Usage:
    class MyGenerator(BaseAssetGenerator):
        DEFAULT_CFG = {"width": 1.0, "height": 2.0}

        def generate(self):
            self._clear_scene()
            obj = self._build()
            return self._finalize(obj, "MyAsset")
"""

import math


class BaseAssetGenerator:
    """Abstract base for all procedural asset generators.

    Subclasses inherit Blender scene utilities and a uniform config/style
    system. The generate() method is the single public entry point.
    """

    DEFAULT_CFG: dict = {}

    def __init__(self, config=None, style=None):
        self.cfg = dict(self.DEFAULT_CFG)
        self.cfg.update(config or {})
        self.style = style if style is not None else self._default_style()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self):
        """Generate and return the primary Blender object."""
        raise NotImplementedError(f"{type(self).__name__}.generate() not implemented")

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------

    def _default_style(self):
        from generators.style import AssetStyle
        return AssetStyle(theme="industrial", material="metal", wear=0.4)

    # ------------------------------------------------------------------
    # Scene utilities (static so subclasses can call without self)
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_scene():
        """Remove all default objects from the scene."""
        import bpy
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)

    @staticmethod
    def _apply_material(obj, style, mat_name, *, color=None, roughness=None,
                        metallic=None, alpha=1.0):
        """Attach a Principled BSDF material to obj.

        If color/roughness/metallic are None the values come from style.
        Pass explicit values to override (e.g. for emissive or glass).
        """
        import bpy
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            c = color if color is not None else style.get_color()
            r = roughness if roughness is not None else style.get_roughness()
            m = metallic if metallic is not None else style.get_metallic()
            bsdf.inputs["Base Color"].default_value = c
            bsdf.inputs["Roughness"].default_value = r
            bsdf.inputs["Metallic"].default_value = m
            if alpha < 1.0:
                bsdf.inputs["Alpha"].default_value = alpha
                mat.blend_method = 'BLEND'
        obj.data.materials.append(mat)
        return mat

    @staticmethod
    def _apply_emission_material(obj, color, strength=5.0, mat_name="Emission"):
        """Attach a purely emissive material (for neon/LED effects)."""
        import bpy
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Clear default BSDF
        for n in nodes:
            nodes.remove(n)

        emit = nodes.new("ShaderNodeEmission")
        emit.inputs["Color"].default_value = (*color[:3], 1.0)
        emit.inputs["Strength"].default_value = strength

        out = nodes.new("ShaderNodeOutputMaterial")
        links.new(emit.outputs["Emission"], out.inputs["Surface"])

        obj.data.materials.append(mat)
        return mat

    @staticmethod
    def _join(parts, name):
        """Join a list of Blender objects into a single mesh."""
        import bpy
        if not parts:
            bpy.ops.mesh.primitive_cube_add(size=0.01)
            return bpy.context.active_object

        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        if len(parts) > 1:
            bpy.ops.object.join()
        result = bpy.context.active_object
        result.name = name
        return result

    @staticmethod
    def _finalize(obj, name, smooth=True, edge_split_angle=30):
        """Rename, shade-smooth, add EdgeSplit, reset origin to world center."""
        import bpy
        obj.name = name
        bpy.context.view_layer.objects.active = obj
        if smooth:
            bpy.ops.object.shade_smooth()
            mod = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
            mod.split_angle = math.radians(edge_split_angle)
        bpy.context.scene.cursor.location = (0, 0, 0)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        return obj
