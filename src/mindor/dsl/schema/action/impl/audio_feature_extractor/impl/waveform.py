from typing import Literal, Union
from pydantic import Field
from .common import CommonAudioFeatureExtractorActionConfig, AudioFeature

class WaveformAudioFeatureExtractorActionConfig(CommonAudioFeatureExtractorActionConfig):
    feature: Literal[AudioFeature.WAVEFORM]
    point_count: Union[int, str] = Field(default=100, description="Number of waveform data points emitted per frame.")
    window_duration: Union[float, int, str] = Field(default="40ms", description="Duration of the sample window per frame, as a duration string (e.g., 40ms, 0.04s) or seconds.")
    summary_mode: Union[Literal[ "peak", "rms" ], str] = Field(default="peak", description="How each downsample bucket is summarized into a single value.")
    rectify: Union[bool, str] = Field(default=True, description="Whether values are returned as absolute magnitudes rather than signed samples.")
