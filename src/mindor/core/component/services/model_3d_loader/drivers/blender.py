from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any
from mindor.dsl.schema.component import Model3DLoaderComponentConfig, Model3DLoaderDriverType, BlenderModel3DLoaderComponentConfig
from mindor.dsl.schema.action import Model3DLoaderActionConfig, BlenderModel3DLoaderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.utils.files import get_temporary_path, get_file_extension
from mindor.core.utils.shell import run_command
from mindor.core.logger import logging
from ..base import Model3DLoaderDriver, register_model_3d_loader_driver
from ..base import ComponentActionContext
from .common import Model3DLoaderAction
import os, shutil, sys

# Blender ships inference code as a top-level `bpy` module reachable from
# `blender --background --python <script>`. The script below is injected via a
# temp file because the operator parameters and import/export dispatch is
# verbose enough that an inline `-c` string would be awkward to read.
_BLENDER_SCRIPT = r"""
import bpy, sys, os

args = sys.argv[sys.argv.index("--") + 1:]
input_path, output_path, output_format, object_name, apply_mods, with_materials, with_anims = args
apply_mods = apply_mods == "1"
with_materials = with_materials == "1"
with_anims = with_anims == "1"

bpy.ops.wm.read_factory_settings(use_empty=True)

ext = os.path.splitext(input_path)[1].lower()
if ext == ".blend":
    bpy.ops.wm.open_mainfile(filepath=input_path)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=input_path)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=input_path)
elif ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=input_path)
elif ext == ".stl":
    bpy.ops.wm.stl_import(filepath=input_path)
elif ext == ".ply":
    bpy.ops.wm.ply_import(filepath=input_path)
else:
    raise RuntimeError("Unsupported input extension: " + ext)

use_selection = bool(object_name)
if use_selection:
    bpy.ops.object.select_all(action='DESELECT')
    if object_name in bpy.data.objects:
        bpy.data.objects[object_name].select_set(True)
        bpy.context.view_layer.objects.active = bpy.data.objects[object_name]
    elif object_name in bpy.data.collections:
        for obj in bpy.data.collections[object_name].all_objects:
            obj.select_set(True)
    else:
        raise RuntimeError("Object or collection '" + object_name + "' not found")

if output_format in ("glb", "gltf"):
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format='GLB' if output_format == "glb" else 'GLTF_EMBEDDED',
        use_selection=use_selection,
        export_apply=apply_mods,
        export_materials='EXPORT' if with_materials else 'NONE',
        export_animations=with_anims,
    )
elif output_format == "obj":
    bpy.ops.wm.obj_export(
        filepath=output_path,
        export_selected_objects=use_selection,
        apply_modifiers=apply_mods,
        export_materials=with_materials,
    )
elif output_format == "fbx":
    bpy.ops.export_scene.fbx(
        filepath=output_path,
        use_selection=use_selection,
        apply_unit_scale=True,
        bake_space_transform=True,
        use_mesh_modifiers=apply_mods,
        add_leaf_bones=False,
        bake_anim=with_anims,
    )
elif output_format == "ply":
    bpy.ops.wm.ply_export(
        filepath=output_path,
        export_selected_objects=use_selection,
        apply_modifiers=apply_mods,
    )
elif output_format == "stl":
    bpy.ops.wm.stl_export(
        filepath=output_path,
        export_selected_objects=use_selection,
        apply_modifiers=apply_mods,
    )
else:
    raise RuntimeError("Unsupported output format: " + output_format)
"""

_BLENDER_SEARCH_PATHS: Dict[str, Tuple[str, ...]] = {
    "darwin": (
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender/Blender.app/Contents/MacOS/Blender",
    ),
    "win32": (
        r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    ),
    "linux": (
        "/usr/bin/blender",
        "/usr/local/bin/blender",
    ),
}

class BlenderModel3DLoaderAction(Model3DLoaderAction):
    config: BlenderModel3DLoaderActionConfig

    def __init__(self, config: BlenderModel3DLoaderActionConfig, binary: str, timeout: float):
        super().__init__(config)

        self.binary: str = binary
        self.timeout: float = timeout

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        object_name        = await context.render_variable(self.config.object_name)
        apply_modifiers    = await context.render_variable(self.config.apply_modifiers)
        include_materials  = await context.render_variable(self.config.include_materials)
        include_animations = await context.render_variable(self.config.include_animations)

        params.update({
            "object_name":        object_name or "",
            "apply_modifiers":    bool(apply_modifiers),
            "include_materials":  bool(include_materials),
            "include_animations": bool(include_animations),
        })

        return params

    async def _load_batch(
        self,
        sources: List[Any],
        format: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Model3DStreamResource]:
        # Blender boot is ~1-3s per invocation, so there is no gain from fanning
        # a batch out in parallel — do them one at a time to keep peak RAM
        # bounded and to let the controller cancel between items.
        results: List[Model3DStreamResource] = []

        for source in sources:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            results.append(await self._load(source, format, params))

        return results

    async def _load(self, source: Any, format: str, params: Dict[str, Any]) -> Model3DStreamResource:
        input_path, spooled = await self._resolve_source_path(source)
        output_path = get_temporary_path(format)
        script_path = get_temporary_path("py")

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(_BLENDER_SCRIPT)

        command = [
            self.binary, "--background", "--python", script_path, "--",
            input_path,
            output_path,
            format,
            params["object_name"],
            "1" if params["apply_modifiers"] else "0",
            "1" if params["include_materials"] else "0",
            "1" if params["include_animations"] else "0",
        ]

        logging.debug("Launching blender: %s", " ".join(command))

        try:
            _, stderr, returncode = await run_command(command, timeout=self.timeout)

            if returncode != 0:
                tail = stderr.decode("utf-8", errors="replace").strip().splitlines()[-40:]

                raise RuntimeError(
                    f"blender export failed (exit {returncode}):\n" + "\n".join(tail)
                )
        finally:
            try:
                os.remove(script_path)
            except FileNotFoundError:
                pass
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        return Model3DStreamResource(
            FileStreamResource(output_path, auto_delete=True),
            format=format,
        )

    async def _resolve_source_path(self, source: Any) -> Tuple[str, bool]:
        stream = await resolve_stream_resource(source)

        if isinstance(stream, FileStreamResource):
            return stream.path, False

        # Blender dispatches by file extension, so a spooled upload needs its
        # original suffix. Pull it from the stream's filename metadata — set
        # when the caller passes `${input.file as file}`.
        extension = get_file_extension(stream.filename) if stream.filename else None
        spooled_path = await save_stream_to_temporary_file(stream, extension=extension)

        return spooled_path, True

@register_model_3d_loader_driver(Model3DLoaderDriverType.BLENDER)
class BlenderModel3DLoaderService(Model3DLoaderDriver):
    config: BlenderModel3DLoaderComponentConfig

    def __init__(self, id: str, config: BlenderModel3DLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.binary: str = self._find_blender(config.binary)
        self.timeout: float = float(config.timeout)

    def _find_blender(self, configured: Optional[str]) -> str:
        if configured:
            if not os.path.exists(configured):
                raise RuntimeError(f"Component '{self.id}': configured blender binary not found: {configured}")

            return configured

        which = shutil.which("blender")

        if which:
            return which

        for path in _BLENDER_SEARCH_PATHS.get(sys.platform, ()):
            if os.path.exists(path):
                return path

        raise RuntimeError(
            f"Component '{self.id}': blender executable not found. "
            "Install Blender from https://blender.org or set component.binary."
        )

    async def _run(self, action: Model3DLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await BlenderModel3DLoaderAction(action, self.binary, self.timeout).run(context)
