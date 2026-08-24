from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioSegmentDetectorActionConfig
from .common import CommonAudioSegmentDetectorComponentConfig, AudioSegmentDetectorDriver

class NativeAudioSegmentDetectorComponentConfig(CommonAudioSegmentDetectorComponentConfig):
    driver: Literal[AudioSegmentDetectorDriver.NATIVE]
    actions: List[AudioSegmentDetectorActionConfig] = Field(default_factory=list)
