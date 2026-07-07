from typing import Literal, Union
from pydantic import Field
from .common import CommonAudioFeatureExtractorActionConfig, AudioFeature

class WaveformAudioFeatureExtractorActionConfig(CommonAudioFeatureExtractorActionConfig):
    feature: Literal[AudioFeature.WAVEFORM]
    point_count: Union[int, str] = Field(default=100, description="Number of data points per frame.")
    window_duration: Union[float, int, str] = Field(default="40ms", description="Window duration per frame (e.g. '40ms', '0.04s', or a number in seconds).")
    summary_mode: Union[Literal[ "peak", "rms" ], str] = Field(default="peak", description="How to summarize each downsample bucket into one value.")
    rectify: Union[bool, str] = Field(default=True, description="If true, return absolute magnitudes (0..1). If false, keep signed values (-1..1).")
