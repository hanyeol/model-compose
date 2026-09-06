from typing import Union, Annotated
from pydantic import Field
from .common import (
    AudioAnalyzerLoudnessActionConfig,
    AudioAnalyzerPeakActionConfig,
    AudioAnalyzerGainActionConfig,
    AudioAnalyzerSilenceActionConfig,
    AudioAnalyzerEnergyActionConfig,
)

FFmpegAudioAnalyzerActionConfig = Annotated[
    Union[
        AudioAnalyzerLoudnessActionConfig,
        AudioAnalyzerPeakActionConfig,
        AudioAnalyzerGainActionConfig,
        AudioAnalyzerSilenceActionConfig,
        AudioAnalyzerEnergyActionConfig,
    ],
    Field(discriminator="metric")
]
