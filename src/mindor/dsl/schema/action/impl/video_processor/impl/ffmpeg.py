from typing import Union, Annotated
from pydantic import Field
from .common import (
    VideoProcessorResizeActionConfig,
    VideoProcessorCropActionConfig,
    VideoProcessorPadActionConfig,
    VideoProcessorFlipActionConfig,
    VideoProcessorRotateActionConfig,
    VideoProcessorSpeedActionConfig,
    VideoProcessorFadeInActionConfig,
    VideoProcessorFadeOutActionConfig,
    VideoProcessorFreezeActionConfig,
    VideoProcessorReverseActionConfig,
    VideoProcessorFpsActionConfig,
)

FFmpegVideoProcessorActionConfig = Annotated[
    Union[
        VideoProcessorResizeActionConfig,
        VideoProcessorCropActionConfig,
        VideoProcessorPadActionConfig,
        VideoProcessorFlipActionConfig,
        VideoProcessorRotateActionConfig,
        VideoProcessorSpeedActionConfig,
        VideoProcessorFadeInActionConfig,
        VideoProcessorFadeOutActionConfig,
        VideoProcessorFreezeActionConfig,
        VideoProcessorReverseActionConfig,
        VideoProcessorFpsActionConfig,
    ],
    Field(discriminator="method")
]
