from typing import Union, Literal, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class AudioAnalyzerMetric(str, Enum):
    LOUDNESS = "loudness"
    PEAK     = "peak"
    GAIN     = "gain"
    CLIPPING = "clipping"
    SILENCE  = "silence"
    ENERGY   = "energy"

class CommonAudioAnalyzerActionConfig(CommonActionConfig):
    metric: AudioAnalyzerMetric = Field(..., description="Kind of measurement performed on the audio.")
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to analyze.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")

class AudioAnalyzerLoudnessActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioAnalyzerMetric.LOUDNESS]
    target_loudness: Union[float, int, str] = Field(default=-23.0, description="Target integrated loudness in LUFS used as the reference by EBU R128.")
    include_timeline: Union[bool, str] = Field(default=False, description="Whether momentary and short-term loudness timelines are included in the result.")

class AudioAnalyzerPeakActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioAnalyzerMetric.PEAK]
    true_peak: Union[bool, str] = Field(default=True, description="Whether inter-sample true-peak (dBTP) is computed alongside sample peak.")

class AudioAnalyzerGainActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioAnalyzerMetric.GAIN]

class AudioAnalyzerClippingActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioAnalyzerMetric.CLIPPING]
    threshold: Union[float, int, str] = Field(default=-0.1, description="Amplitude threshold in dBFS above which samples are treated as clipped.")
    min_consecutive_length: Union[int, str] = Field(default=3, description="Minimum number of consecutive over-threshold samples required to count as a clipping region.")

class AudioAnalyzerSilenceActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioAnalyzerMetric.SILENCE]
    threshold: Union[float, int, str] = Field(default=-60.0, description="Amplitude threshold in dBFS below which audio is considered silent.")
    min_duration: Union[float, int, str] = Field(default="0.5s", description="Minimum duration of below-threshold audio required to count as a silence region.")

class AudioAnalyzerEnergyActionConfig(CommonAudioAnalyzerActionConfig):
    metric: Literal[AudioAnalyzerMetric.ENERGY]
    threshold: Union[float, int, str] = Field(default=-40.0, description="Momentary loudness threshold in LUFS above which audio is considered active.")
    segment_duration: Optional[Union[float, int, str]] = Field(default=None, description="Length of the segment scanned for the loudest section; omit to skip segment search.")
    resolution: Union[float, int, str] = Field(default="1s", description="Downsampling interval used to aggregate momentary loudness into the returned profile.")
