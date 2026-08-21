from typing import Union, Annotated
from pydantic import Field
from .impl import *

AudioAnalyzerActionConfig = Annotated[
    Union[
        LoudnessAudioAnalyzerActionConfig,
        PeakAudioAnalyzerActionConfig,
        GainAudioAnalyzerActionConfig,
        ClippingAudioAnalyzerActionConfig,
        SilenceAudioAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
