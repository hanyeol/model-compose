from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioExtractorActionConfig
from .common import CommonAudioExtractorComponentConfig, AudioExtractorDriverType

class FFmpegAudioExtractorComponentConfig(CommonAudioExtractorComponentConfig):
    driver: Literal[AudioExtractorDriverType.FFMPEG]
    actions: List[AudioExtractorActionConfig] = Field(default_factory=list)
