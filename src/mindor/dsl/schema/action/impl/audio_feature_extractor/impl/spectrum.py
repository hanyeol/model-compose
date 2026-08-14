from typing import Literal, Optional, Union
from pydantic import Field
from .common import CommonAudioFeatureExtractorActionConfig, AudioFeature

class SpectrumAudioFeatureExtractorActionConfig(CommonAudioFeatureExtractorActionConfig):
    feature: Literal[AudioFeature.SPECTRUM]
    band_count: Union[int, str] = Field(default=32, description="Number of frequency bands in the output spectrum.")
    min_frequency: Union[float, int, str] = Field(default=40.0, description="Lowest frequency in Hz included in the band grid.")
    max_frequency: Optional[Union[float, int, str]] = Field(default=None, description="Highest frequency in Hz included in the band grid; defaults to the Nyquist frequency.")
    frequency_scale: Union[Literal[ "log", "linear" ], str] = Field(default="log", description="Scale used to distribute frequency bands.")
    window_size: Union[int, str] = Field(default=2048, description="FFT window size in samples.")
    window_type: Union[Literal[ "hann", "hamming", "blackman" ], str] = Field(default="hann", description="Window function applied to samples before the FFT.")
    normalize_mode: Union[Literal[ "peak-percentile", "none" ], str] = Field(default="peak-percentile", description="Strategy used to normalize band amplitudes.")
    percentile: Union[float, int, str] = Field(default=99.0, description="Percentile of amplitudes used as the reference by `peak-percentile` normalization.")
