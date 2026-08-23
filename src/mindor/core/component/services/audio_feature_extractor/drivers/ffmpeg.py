from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Tuple, Any
from mindor.dsl.schema.component import AudioFeatureExtractorComponentConfig
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.utils.audio import is_streamable_audio_format
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ..base import AudioFeatureExtractorService, AudioFeatureExtractorDriver, register_audio_feature_extractor_service
from ..base import ComponentActionContext
from .common import AudioFeatureExtractorAction
import os

if TYPE_CHECKING:
    import numpy as np

class FFmpegAudioFeatureExtractorAction(AudioFeatureExtractorAction):
    async def _decode_pcm(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        """Decode any audio source into mono float32 PCM in [-1, 1] via ffmpeg."""
        import numpy as np

        input_path, spooled = await self._resolve_input_path(source)

        command = [ "ffmpeg", "-hide_banner", "-loglevel", "error" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])
        command.extend([ "-f", "s16le", "-ac", "1", "-ar", str(sample_rate), "pipe:1" ])

        try:
            process, stdout, stderr = await run_subprocess(
                command,
                source.stream if input_path is None else None,
                stdout_handler=lambda r: r.read(),
                stderr_handler=lambda r: r.read(),
            )
            if process.returncode != 0:
                error_message = stderr.decode("utf-8", errors="replace") if stderr else ""
                raise RuntimeError(f"ffmpeg PCM decode failed (exit code {process.returncode}): {error_message}")
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        return np.frombuffer(stdout, dtype=np.int16).astype(np.float32) / 32768.0

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

@register_audio_feature_extractor_service(AudioFeatureExtractorDriver.FFMPEG)
class FFmpegAudioFeatureExtractorService(AudioFeatureExtractorService):
    def __init__(self, id: str, config: AudioFeatureExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "numpy" ]

    async def _run(
        self,
        action: AudioFeatureExtractorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await FFmpegAudioFeatureExtractorAction(action).run(context)
