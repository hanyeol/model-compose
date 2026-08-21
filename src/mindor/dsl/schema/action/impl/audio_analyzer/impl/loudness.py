from typing import Literal, Union
from pydantic import Field
from .common import CommonAudioAnalyzerActionConfig, AudioMetric

class LoudnessAudioAnalyzerActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioMetric.LOUDNESS]
    target_loudness: Union[float, int, str] = Field(default=-23.0, description="Target integrated loudness in LUFS used as the reference by EBU R128.")
    include_timeline: Union[bool, str] = Field(default=False, description="Whether momentary and short-term loudness timelines are included in the result.")
