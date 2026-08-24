from typing import Union
from pydantic import Field
from .common import CommonAudioSegmentDetectorActionConfig

class FFmpegAudioSegmentDetectorActionConfig(CommonAudioSegmentDetectorActionConfig):
    silence_threshold: Union[float, int, str] = Field(default=-30.0, description="Silence detection threshold in dBFS passed to ffmpeg's silencedetect filter.")
