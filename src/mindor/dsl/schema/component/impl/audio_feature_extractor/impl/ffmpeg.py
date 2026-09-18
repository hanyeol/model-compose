from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from .common import CommonAudioFeatureExtractorComponentConfig, AudioFeatureExtractorDriverType

class FFmpegAudioFeatureExtractorComponentConfig(CommonAudioFeatureExtractorComponentConfig):
    driver: Literal[AudioFeatureExtractorDriverType.FFMPEG]
    actions: List[AudioFeatureExtractorActionConfig] = Field(default_factory=list)
