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
    VideoProcessorResampleActionConfig,
    VideoProcessorAdjustColorActionConfig,
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
        VideoProcessorResampleActionConfig,
        VideoProcessorAdjustColorActionConfig,
    ],
    Field(discriminator="method")
]
