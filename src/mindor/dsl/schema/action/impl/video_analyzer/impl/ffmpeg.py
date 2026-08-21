from typing import Union, Annotated
from pydantic import Field
from .common import (
    BlackVideoAnalyzerActionConfig,
    FreezeVideoAnalyzerActionConfig,
    BrightnessVideoAnalyzerActionConfig,
    MotionVideoAnalyzerActionConfig,
)

FFmpegVideoAnalyzerActionConfig = Annotated[
    Union[
        BlackVideoAnalyzerActionConfig,
        FreezeVideoAnalyzerActionConfig,
        BrightnessVideoAnalyzerActionConfig,
        MotionVideoAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
