from typing import Literal
from .common import CommonAudioAnalyzerActionConfig, AudioMetric

class GainAudioAnalyzerActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioMetric.GAIN]
