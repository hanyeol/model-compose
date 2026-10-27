from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any
from mindor.dsl.schema.component import Model3DLoaderComponentConfig, Model3DLoaderDriverType
from mindor.dsl.schema.action import Model3DLoaderActionConfig, NativeModel3DLoaderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.utils.files import get_temporary_path, get_file_extension
from mindor.core.logger import logging
from ..base import Model3DLoaderDriver, register_model_3d_loader_driver
from ..base import ComponentActionContext
from .common import Model3DLoaderAction
import asyncio, os

class NativeModel3DLoaderAction(Model3DLoaderAction):
    config: NativeModel3DLoaderActionConfig

    async def _load_batch(
        self,
        sources: List[Any],
        format: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Model3DStreamResource]:
        return await asyncio.gather(*[
            self._load(source, format) for source in sources
        ])

    async def _load(self, source: Any, format: str) -> Model3DStreamResource:
        input_path, spooled = await self._resolve_source_path(source)
        input_format = get_file_extension(input_path)
        output_path = get_temporary_path(format)

        logging.debug("Loading 3D model from '%s' (input=%s) -> format '%s'", input_path, input_format, format)

        try:
            await asyncio.to_thread(self._convert, input_path, input_format, output_path, format)
        finally:
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

        extension = get_file_extension(stream.filename) if stream.filename else None
        spooled_path = await save_stream_to_temporary_file(stream, extension=extension)

        return spooled_path, True

    @staticmethod
    def _convert(input_path: str, input_format: Optional[str], output_path: str, format: str) -> None:
        import trimesh

        scene_or_mesh = trimesh.load(
            input_path,
            file_type=input_format,
            force="mesh" if format in ("stl", "ply") else None,
        )

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

@register_model_3d_loader_driver(Model3DLoaderDriverType.NATIVE)
class NativeModel3DLoaderService(Model3DLoaderDriver):
    def __init__(self, id: str, config: Model3DLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "trimesh" ]

    async def _run(self, action: Model3DLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await NativeModel3DLoaderAction(action).run(context)
