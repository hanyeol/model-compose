from typing import Union, Annotated
from pydantic import Field
from .common import (
    LoudnessAudioAnalyzerActionConfig,
    PeakAudioAnalyzerActionConfig,
    GainAudioAnalyzerActionConfig,
    ClippingAudioAnalyzerActionConfig,
    SilenceAudioAnalyzerActionConfig,
)

FFmpegAudioAnalyzerActionConfig = Annotated[
    Union[
        LoudnessAudioAnalyzerActionConfig,
        PeakAudioAnalyzerActionConfig,
        GainAudioAnalyzerActionConfig,
        ClippingAudioAnalyzerActionConfig,
        SilenceAudioAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
