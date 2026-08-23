from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Tuple, Any
from mindor.dsl.schema.component import AudioSynchronizerComponentConfig
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.utils.audio import is_streamable_audio_format
from mindor.core.utils.ffmpeg.audio import decode_pcm_from_file, decode_pcm_from_stream
from mindor.core.logger import logging
from ..base import AudioSynchronizerService, AudioSynchronizerDriver, register_audio_synchronizer_service
from ..base import ComponentActionContext
from .common import AudioSynchronizerAction
import os

if TYPE_CHECKING:
    import numpy as np

class FFmpegAudioSynchronizerAction(AudioSynchronizerAction):
    async def _decode_pcm(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        input_path, spooled = await self._resolve_input_path(source)

        try:
            if input_path is not None:
                return await decode_pcm_from_file(input_path, sample_rate)

            return await decode_pcm_from_stream(source.stream, sample_rate, format=source.format)
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (mp3, wav, ...): feed via pipe:0 (returns None path).
        - Otherwise (m4a/mp4-wrapped/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if is_streamable_audio_format(source.format):
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before decoding")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

@register_audio_synchronizer_service(AudioSynchronizerDriver.FFMPEG)
class FFmpegAudioSynchronizerService(AudioSynchronizerService):
    def __init__(self, id: str, config: AudioSynchronizerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "numpy" ]

    async def _run(
        self,
        action: AudioSynchronizerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await FFmpegAudioSynchronizerAction(action).run(context)
