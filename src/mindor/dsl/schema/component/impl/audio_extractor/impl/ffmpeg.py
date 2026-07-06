from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioExtractorActionConfig
from .common import CommonAudioExtractorComponentConfig, AudioExtractorDriver

class FfmpegAudioExtractorComponentConfig(CommonAudioExtractorComponentConfig):
    driver: Literal[AudioExtractorDriver.FFMPEG]
    actions: List[AudioExtractorActionConfig] = Field(default_factory=list)
