from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MediaInspectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.audio import is_streamable_audio_format
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.logger import logging
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import os

class MediaInspectorAction(ComponentAction):
    def __init__(self, config: MediaInspectorActionConfig):
        self.config: MediaInspectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        media      = await context.render_media(self.config.media)
        return_raw = await context.render_scalar(self.config.return_raw, bool, True)
        batch_size = await context.render_variable(self.config.batch_size)

        is_single_input  = not isinstance(media, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(media, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(media, batch_size=batch_size or 1):
                    batch_results = await self._inspect_batch(batch_sources, return_raw, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_sources in BatchSourceIterator(media, batch_size=batch_size or 1):
                batch_results = await self._inspect_batch(batch_sources, return_raw, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    @staticmethod
    async def _resolve_input_path(source: MediaSource) -> Tuple[Optional[str], bool]:
        """Decide how the inspector CLI should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable audio/video format (mp3, wav, mpegts, flv, ...): feed via
          stdin (returns None path); the driver is expected to pass the stream
          to a subprocess. Container-heavy formats (mp4/mov/mkv, images) still
          need seekable input and are spooled to a temp file.
        - Otherwise: spool the stream to a temp file.

        Returns (input_path, spooled) — `input_path is None` means the driver
        should read from stdin; `spooled=True` means the caller owns the temp
        file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if is_streamable_audio_format(source.format) or is_streamable_video_format(source.format):
            return None, False

        logging.debug("media inspector input is not streamable; spooling to a temp file before probing")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    @staticmethod
    def _remove_file(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    @abstractmethod
    async def _inspect_batch(
        self,
        sources: List[MediaSource],
        return_raw: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        """Return, per input source, a normalized metadata dict.

        Each `MediaSource` carries the caller's format/attrs hints. When
        `return_raw` is true the driver's raw output should be included
        under `raw` in each result.
        """
        pass
