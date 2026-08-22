from __future__ import annotations

from typing import Optional, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import AudioCaptureActionConfig, AudioCaptureSource
from ....action.media import MediaComponentAction
from ..base import ComponentActionContext

class AudioCaptureAction(MediaComponentAction):
    def __init__(self, config: AudioCaptureActionConfig):
        self.config: AudioCaptureActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._capture(params)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        source      = await context.render_variable(self.config.source)
        device      = await context.render_variable(self.config.device) if self.config.device is not None else None
        sample_rate = await context.render_scalar(self.config.sample_rate, int, None) if self.config.sample_rate is not None else None
        channels    = await context.render_scalar(self.config.channels, int, None) if self.config.channels is not None else None
        encoding    = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else None
        duration    = await context.render_scalar(self.config.duration, "time", None)

        try:
            source = AudioCaptureSource(source)
        except ValueError:
            raise ValueError(f"Invalid source: {source}")

        if sample_rate is not None and sample_rate <= 0:
            raise ValueError(f"'sample_rate' must be > 0, got {sample_rate}")

        if channels is not None and channels <= 0:
            raise ValueError(f"'channels' must be > 0, got {channels}")

        if duration is not None and duration <= 0:
            raise ValueError(f"'duration' must be > 0, got {duration}")

        return {
            "source":      source,
            "device":      device,
            "sample_rate": sample_rate,
            "channels":    channels,
            "encoding":    encoding,
            "duration":    duration,
        }

    @abstractmethod
    async def _capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run the capture and return a dict shaped like:

            { "audio": AudioStreamResource,
              "capture_pts": float }

        `capture_pts` is a monotonic wall-clock anchor (seconds) taken when
        capture starts, so downstream consumers can align chunks to an absolute
        broadcast timeline.
        """
        pass
