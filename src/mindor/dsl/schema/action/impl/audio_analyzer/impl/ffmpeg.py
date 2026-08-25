from typing import Union, Annotated
from pydantic import Field
from .common import (
    AudioAnalyzerLoudnessActionConfig,
    AudioAnalyzerPeakActionConfig,
    AudioAnalyzerGainActionConfig,
    AudioAnalyzerClippingActionConfig,
    AudioAnalyzerSilenceActionConfig,
    AudioAnalyzerEnergyActionConfig,
)

FFmpegAudioAnalyzerActionConfig = Annotated[
    Union[
        AudioAnalyzerLoudnessActionConfig,
        AudioAnalyzerPeakActionConfig,
        AudioAnalyzerGainActionConfig,
        AudioAnalyzerClippingActionConfig,
        AudioAnalyzerSilenceActionConfig,
        AudioAnalyzerEnergyActionConfig,
    ],
    Field(discriminator="metric")
]
