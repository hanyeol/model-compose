from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from .common import CommonAudioFeatureExtractorComponentConfig, AudioFeatureExtractorDriver

class FFmpegAudioFeatureExtractorComponentConfig(CommonAudioFeatureExtractorComponentConfig):
    driver: Literal[AudioFeatureExtractorDriver.FFMPEG]
    actions: List[AudioFeatureExtractorActionConfig] = Field(default_factory=list)
