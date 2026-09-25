from __future__ import annotations

from typing import List, Optional, Dict, Any
from mindor.dsl.schema.component import Model3DConverterComponentConfig
from mindor.dsl.schema.action import Model3DConverterActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.files import get_temporary_path, get_file_extension
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import Model3DConverterDriver, Model3DConverterDriverType, register_model_3d_converter_driver
from ..base import ComponentActionContext
from .common import Model3DConverterAction
import asyncio, os

class NativeModel3DConverterAction(Model3DConverterAction):
    async def _convert_batch(
        self,
        models: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Model3DStreamResource]:
        return await asyncio.gather(*[
            self._convert(model, params["format"], cancellation_token) for model in models
        ])

    async def _convert(
        self,
        source: MediaSource,
        format: str,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Model3DStreamResource:
        input_path, spooled = await MediaInputPathResolver().resolve(source, default_format=source.format)
        input_format = source.format or (get_file_extension(input_path) if input_path else None)
        output_path = get_temporary_path(format)

        if not input_format:
            raise RuntimeError("Cannot determine 3D model input format.")

        logging.debug("Converting 3D model from '%s' to '%s' (input=%s)", input_format, format, input_path)

        try:
            await asyncio.to_thread(self._export, input_path, input_format, output_path, format)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug("3D model conversion completed: '%s'", output_path)

        return Model3DStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    @staticmethod
    def _export(input_path: str, input_format: str, output_path: str, format: str) -> None:
        import trimesh

        scene_or_mesh = trimesh.load(input_path, file_type=input_format, force=None)
        export_params: Dict[str, Any] = { "file_type": format }

        if format == "gltf":
            export_params["embed_buffers"] = True

        try:
            scene_or_mesh.export(output_path, **export_params)
        except ValueError as error:
            raise RuntimeError(
                f"trimesh cannot export to format '{format}'. "
                f"Supported formats depend on the input mesh type; original error: {error}"
            ) from error

@register_model_3d_converter_driver(Model3DConverterDriverType.NATIVE)
class NativeModel3DConverterService(Model3DConverterDriver):
    def __init__(self, id: str, config: Model3DConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "trimesh" ]

    async def _run(self, action: Model3DConverterActionConfig, context: ComponentActionContext) -> Any:
        return await NativeModel3DConverterAction(action).run(context)
