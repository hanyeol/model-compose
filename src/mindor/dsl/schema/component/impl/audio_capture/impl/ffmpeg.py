from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioCaptureActionConfig
from .common import CommonAudioCaptureComponentConfig, AudioCaptureDriverType

class FFmpegAudioCaptureComponentConfig(CommonAudioCaptureComponentConfig):
    driver: Literal[AudioCaptureDriverType.FFMPEG]
    actions: List[AudioCaptureActionConfig] = Field(default_factory=list)
