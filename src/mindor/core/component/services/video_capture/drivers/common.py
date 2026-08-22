from __future__ import annotations

from typing import Optional, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import VideoCaptureActionConfig, VideoCaptureSource
from ....action.media import MediaComponentAction
from ..base import ComponentActionContext

class VideoCaptureAction(MediaComponentAction):
    def __init__(self, config: VideoCaptureActionConfig):
        self.config: VideoCaptureActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._capture(params)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        source       = await context.render_variable(self.config.source)
        device       = await context.render_variable(self.config.device) if self.config.device is not None else None
        resolution   = await self._resolve_resolution(context) if self.config.resolution is not None else None
        framerate    = await context.render_scalar(self.config.framerate, float)
        pixel_format = await context.render_variable(self.config.pixel_format) if self.config.pixel_format is not None else None
        encoding     = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else None
        duration     = await context.render_scalar(self.config.duration, "time", None)

        try:
            source = VideoCaptureSource(source)
        except ValueError:
            raise ValueError(f"Invalid source: {source}")

        if framerate <= 0:
            raise ValueError(f"'framerate' must be > 0, got {framerate}")

        if duration is not None and duration <= 0:
            raise ValueError(f"'duration' must be > 0, got {duration}")

        return {
            "source":       source,
            "device":       device,
            "resolution":   resolution,
            "framerate":    framerate,
            "pixel_format": pixel_format,
            "encoding":     encoding,
            "duration":     duration,
        }

    async def _resolve_resolution(self, context: ComponentActionContext) -> Dict[str, int]:
        width  = await context.render_scalar(self.config.resolution.width, int)
        height = await context.render_scalar(self.config.resolution.height, int)

        if width <= 0 or height <= 0:
            raise ValueError(f"resolution must be > 0, got width={width}, height={height}")

        return { "width": width, "height": height }

    @abstractmethod
    async def _capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run the capture and return a dict shaped like:

            { "video": VideoStreamResource,
              "capture_pts": float }
        """
        pass
