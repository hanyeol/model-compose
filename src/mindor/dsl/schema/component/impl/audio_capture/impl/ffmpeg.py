from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioCaptureActionConfig
from .common import CommonAudioCaptureComponentConfig, AudioCaptureDriver

class FFmpegAudioCaptureComponentConfig(CommonAudioCaptureComponentConfig):
    driver: Literal[AudioCaptureDriver.FFMPEG]
    actions: List[AudioCaptureActionConfig] = Field(default_factory=list)
