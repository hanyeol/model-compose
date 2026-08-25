from typing import Union, Annotated
from pydantic import Field
from .common import (
    AudioAnalyzerLoudnessActionConfig,
    AudioAnalyzerPeakActionConfig,
    AudioAnalyzerGainActionConfig,
    AudioAnalyzerClippingActionConfig,
    AudioAnalyzerSilenceActionConfig,
)

FFmpegAudioAnalyzerActionConfig = Annotated[
    Union[
        AudioAnalyzerLoudnessActionConfig,
        AudioAnalyzerPeakActionConfig,
        AudioAnalyzerGainActionConfig,
        AudioAnalyzerClippingActionConfig,
        AudioAnalyzerSilenceActionConfig,
    ],
    Field(discriminator="metric")
]
