from __future__ import annotations

from typing import Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import Model3DRendererActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
from ....action.base import ComponentAction

class Model3DRendererAction(ComponentAction):
    def __init__(self, config: Model3DRendererActionConfig):
        self.config: Model3DRendererActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        model_3d   = await context.render_model_3d(self.config.model_3d)
        camera     = await context.render_variable(self.config.camera)
        lighting   = await context.render_variable(self.config.lighting)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_shared_params(context)

        is_single_input    = not any(isinstance(value, (list, StreamIterator, AsyncIterator)) for value in (model_3d, camera, lighting))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (model_3d, camera, lighting))
        is_direct_output   = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_models, batch_cameras, batch_lightings in BatchSourceIterator((model_3d, camera, lighting), batch_size=batch_size or 1):
                    batch_results = await self._render_batch(batch_models, batch_cameras, batch_lightings, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[ImageStreamResource] = []
            async for batch_models, batch_cameras, batch_lightings in BatchSourceIterator((model_3d, camera, lighting), batch_size=batch_size or 1):
                batch_results = await self._render_batch(batch_models, batch_cameras, batch_lightings, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_shared_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        format     = await context.render_scalar(self.config.format, str, "png")
        width      = await context.render_scalar(self.config.width, int, 512)
        height     = await context.render_scalar(self.config.height, int, 512)
        fit        = await context.render_scalar(self.config.fit, str, "contain")
        background = await context.render_scalar(self.config.background, "color")

        # jpeg has no alpha; fall back to opaque white when the caller left the
        # canvas transparent (background is None or carries alpha == 0).
        if format == "jpeg" and (background is None or background[3] == 0):
            background = (255, 255, 255, 255)

        return {
            "format": format,
            "width": width,
            "height": height,
            "fit": fit,
            "background": background,
        }

    @abstractmethod
    async def _render_batch(
        self,
        models: List[MediaSource],
        cameras: List[Optional[Dict[str, Any]]],
        lightings: List[Optional[Dict[str, Any]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[ImageStreamResource]:
        pass
