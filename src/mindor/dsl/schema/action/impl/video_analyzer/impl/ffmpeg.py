from typing import Union, Annotated
from pydantic import Field
from .common import (
    VideoAnalyzerBlackActionConfig,
    VideoAnalyzerFreezeActionConfig,
    VideoAnalyzerBrightnessActionConfig,
    VideoAnalyzerMotionActionConfig,
)

FFmpegVideoAnalyzerActionConfig = Annotated[
    Union[
        VideoAnalyzerBlackActionConfig,
        VideoAnalyzerFreezeActionConfig,
        VideoAnalyzerBrightnessActionConfig,
        VideoAnalyzerMotionActionConfig,
    ],
    Field(discriminator="metric")
]
