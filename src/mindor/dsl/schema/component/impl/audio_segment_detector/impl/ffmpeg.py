from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioSegmentDetectorActionConfig
from .common import CommonAudioSegmentDetectorComponentConfig, AudioSegmentDetectorDriver

class FFmpegAudioSegmentDetectorComponentConfig(CommonAudioSegmentDetectorComponentConfig):
    driver: Literal[AudioSegmentDetectorDriver.FFMPEG]
    actions: List[AudioSegmentDetectorActionConfig] = Field(default_factory=list)
