from typing import Literal, Union
from pydantic import Field
from .common import CommonAudioAnalyzerActionConfig, AudioMetric

class ClippingAudioAnalyzerActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioMetric.CLIPPING]
    threshold: Union[float, int, str] = Field(default=-0.1, description="Amplitude threshold in dBFS above which samples are treated as clipped.")
    min_consecutive_samples: Union[int, str] = Field(default=3, description="Minimum consecutive over-threshold samples required to count as a clipping region.")
