from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Any
from mindor.dsl.schema.component import AudioFeatureExtractorComponentConfig
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.audio import AudioStream, decode_pcm_to_waveform
from mindor.core.utils.ffmpeg.audio import load_pcm_from_file, load_pcm_from_stream
from ....action.media import MediaInputPathResolver
from ..base import AudioFeatureExtractorService, AudioFeatureExtractorDriver, register_audio_feature_extractor_service
from ..base import ComponentActionContext
from .common import AudioFeatureExtractorAction
import os

if TYPE_CHECKING:
    import numpy as np

class FFmpegAudioFeatureExtractorAction(AudioFeatureExtractorAction):
    async def _load_pcm_samples(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "audio" ])

        try:
            if input_path is not None:
                pcm = await load_pcm_from_file(input_path, sample_rate, channels=1)
            else:
                pcm = await load_pcm_from_stream(
                    AudioStream(source.stream, source.format), sample_rate, channels=1,
                )

            return decode_pcm_to_waveform(pcm, "s16le", dtype="float32")
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

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
