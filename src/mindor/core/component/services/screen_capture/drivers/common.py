from __future__ import annotations

from typing import Optional, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import (
    ScreenCaptureActionConfig,
    ScreenCaptureVideoSource,
    ScreenCaptureAudioSource,
)
from ....action.media import MediaComponentAction
from ..base import ComponentActionContext

class ScreenCaptureAction(MediaComponentAction):
    def __init__(self, config: ScreenCaptureActionConfig):
        self.config: ScreenCaptureActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._capture(params)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        video_source  = await context.render_variable(self.config.video_source)
        audio_source  = await context.render_variable(self.config.audio_source)
        include_video = await context.render_scalar(self.config.include_video, bool)
        include_audio = await context.render_scalar(self.config.include_audio, bool)
        display       = await context.render_scalar(self.config.display, int)
        region        = await self._resolve_region(context) if self.config.region is not None else None
        window        = await self._resolve_window(context) if self.config.window is not None else None
        framerate     = await context.render_scalar(self.config.framerate, float)
        encoding      = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else None
        duration      = await context.render_scalar(self.config.duration, "time", None)

        try:
            video_source = ScreenCaptureVideoSource(video_source)
        except ValueError:
            raise ValueError(f"Invalid video_source: {video_source}")

        try:
            audio_source = ScreenCaptureAudioSource(audio_source)
        except ValueError:
            raise ValueError(f"Invalid audio_source: {audio_source}")

        if framerate <= 0:
            raise ValueError(f"'framerate' must be > 0, got {framerate}")

        if duration is not None and duration <= 0:
            raise ValueError(f"'duration' must be > 0, got {duration}")

        if video_source == ScreenCaptureVideoSource.REGION and region is None:
            raise ValueError("'region' must be provided when video_source='region'.")

        if video_source == ScreenCaptureVideoSource.WINDOW and window is None:
            raise ValueError("'window' must be provided when video_source='window'.")

        return {
            "video_source":  video_source,
            "display":       display,
            "region":        region,
            "window":        window,
            "include_video": include_video,
            "include_audio": include_audio,
            "audio_source":  audio_source,
            "framerate":     framerate,
            "encoding":      encoding,
            "duration":      duration,
        }

    async def _resolve_region(self, context: ComponentActionContext) -> Dict[str, int]:
        x      = await context.render_scalar(self.config.region.x, int)
        y      = await context.render_scalar(self.config.region.y, int)
        width  = await context.render_scalar(self.config.region.width, int)
        height = await context.render_scalar(self.config.region.height, int)

        if width <= 0 or height <= 0:
            raise ValueError(f"region size must be > 0, got width={width}, height={height}")

        if x < 0 or y < 0:
            raise ValueError(f"region origin must be >= 0, got x={x}, y={y}")

        return { "x": x, "y": y, "width": width, "height": height }

    async def _resolve_window(self, context: ComponentActionContext) -> Dict[str, Optional[str]]:
        title = await context.render_scalar(self.config.window.title, str, None) if self.config.window.title else None
        app   = await context.render_scalar(self.config.window.app, str, None) if self.config.window.app else None

        if not title and not app:
            raise ValueError("window selector must include at least one of 'title' or 'app'.")

        return { "title": title, "app": app }

    @abstractmethod
    async def _capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run the capture and return a dict shaped like:

            { "video": VideoStreamResource | None,
              "audio": AudioStreamResource | None,
              "capture_pts": float }

        `capture_pts` is a monotonic wall-clock anchor (seconds) taken when
        capture starts, so downstream consumers can align chunks to an absolute
        broadcast timeline.
        """
        pass
