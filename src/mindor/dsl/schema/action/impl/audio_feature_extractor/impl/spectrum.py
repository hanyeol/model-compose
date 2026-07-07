from typing import Literal, Optional, Union
from pydantic import Field
from .common import CommonAudioFeatureExtractorActionConfig, AudioFeature

class SpectrumAudioFeatureExtractorActionConfig(CommonAudioFeatureExtractorActionConfig):
    feature: Literal[AudioFeature.SPECTRUM]
    band_count: Union[int, str] = Field(default=32, description="Number of frequency bands.")
    min_frequency: Union[float, int, str] = Field(default=40.0, description="Lowest frequency (Hz) included in the band grid.")
    max_frequency: Optional[Union[float, int, str]] = Field(default=None, description="Highest frequency (Hz). Defaults to Nyquist (sample_rate / 2) when omitted.")
    frequency_scale: Union[Literal[ "log", "linear" ], str] = Field(default="log", description="Frequency band distribution scale.")
    window_size: Union[int, str] = Field(default=2048, description="FFT window size in samples.")
    window_type: Union[Literal[ "hann", "hamming", "blackman" ], str] = Field(default="hann", description="Window function type applied before FFT.")
    normalize_mode: Union[Literal[ "peak-percentile", "none" ], str] = Field(default="peak-percentile", description="Amplitude normalization strategy.")
    percentile: Union[float, int, str] = Field(default=99.0, description="Percentile used by 'peak-percentile' normalization.")
