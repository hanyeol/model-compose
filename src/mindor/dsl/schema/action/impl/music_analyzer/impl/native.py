from typing import Union, Annotated
from pydantic import Field
from .common import (
    MusicAnalyzerBeatsActionConfig,
    MusicAnalyzerOnsetsActionConfig,
    MusicAnalyzerTempogramActionConfig,
    MusicAnalyzerActivityActionConfig,
    MusicAnalyzerKeyActionConfig,
    MusicAnalyzerChromaActionConfig,
    MusicAnalyzerTonnetzActionConfig,
    MusicAnalyzerBrightnessActionConfig,
    MusicAnalyzerFlatnessActionConfig,
    MusicAnalyzerHarmonicityActionConfig,
)

NativeMusicAnalyzerActionConfig = Annotated[
    Union[
        MusicAnalyzerBeatsActionConfig,
        MusicAnalyzerOnsetsActionConfig,
        MusicAnalyzerTempogramActionConfig,
        MusicAnalyzerActivityActionConfig,
        MusicAnalyzerKeyActionConfig,
        MusicAnalyzerChromaActionConfig,
        MusicAnalyzerTonnetzActionConfig,
        MusicAnalyzerBrightnessActionConfig,
        MusicAnalyzerFlatnessActionConfig,
        MusicAnalyzerHarmonicityActionConfig,
    ],
    Field(discriminator="metric")
]
