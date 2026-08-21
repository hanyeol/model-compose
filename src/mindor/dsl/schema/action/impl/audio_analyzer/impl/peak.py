from typing import Literal, Union
from pydantic import Field
from .common import CommonAudioAnalyzerActionConfig, AudioMetric

class PeakAudioAnalyzerActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioMetric.PEAK]
    true_peak: Union[bool, str] = Field(default=True, description="Whether inter-sample true-peak (dBTP) is computed alongside sample peak.")
