from typing import Literal, Union
from pydantic import Field
from .common import CommonAudioAnalyzerActionConfig, AudioMetric

class SilenceAudioAnalyzerActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioMetric.SILENCE]
    threshold: Union[float, int, str] = Field(default=-60.0, description="Amplitude threshold in dBFS below which audio is considered silent.")
    min_duration: Union[float, int, str] = Field(default="0.5s", description="Minimum duration of below-threshold audio required to count as a silence region.")
