from __future__ import annotations

from typing import Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import AudioPlaybackActionConfig, AudioPlaybackSink
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class AudioPlaybackAction:
    def __init__(self, config: AudioPlaybackActionConfig):
        self.config: AudioPlaybackActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        # Playback has no return value, so single/list/stream inputs all collapse
        # into one sequential consume-and-play loop. BatchSourceIterator normalizes
        # AsyncIterator/StreamIterator/list/single into batches, and batch_size
        # controls the fan-out to the sink when multiple inputs arrive together.
        async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
            await self._process_batch(batch_audios, params, loop, context.cancellation_token)

        return None

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        sink     = await context.render_variable(self.config.sink)
        device   = await context.render_variable(self.config.device)   if self.config.device   is not None else None
        volume   = await context.render_variable(self.config.volume)
        duration = await context.render_variable(self.config.duration) if self.config.duration is not None else None
        blocking = await context.render_variable(self.config.blocking)

        return {
            "sink":     AudioPlaybackSink(sink) if not isinstance(sink, AudioPlaybackSink) else sink,
            "device":   device,
            "volume":   float(volume),
            "duration": parse_time(duration) if duration is not None else None,
            "blocking": bool(blocking),
        }

    async def _process_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        await asyncio.gather(*[
            self._process(audio, params, loop, cancellation_token) for audio in audios
        ])

    async def _process(
        self,
        audio: Optional[MediaSource],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        if audio is None:
            logging.debug("Audio playback skipped because no audio was provided.")
            return

        await self._play(audio, params, loop, cancellation_token)

    @abstractmethod
    async def _play(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        pass
