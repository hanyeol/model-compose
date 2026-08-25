from typing import Union
from pydantic import Field
from .common import CommonAudioSilenceDetectorActionConfig

class FFmpegAudioSilenceDetectorActionConfig(CommonAudioSilenceDetectorActionConfig):
    silence_threshold: Union[float, int, str] = Field(default=-30.0, description="Silence detection threshold in dBFS passed to ffmpeg's silencedetect filter.")
    min_silence_duration: Union[float, int, str] = Field(default="500ms", description="Minimum duration a quiet run must last to be reported as silence.")
