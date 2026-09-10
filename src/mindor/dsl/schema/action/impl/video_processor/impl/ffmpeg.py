from typing import Union, Annotated
from pydantic import Field
from .common import (
    VideoProcessorResizeActionConfig,
    VideoProcessorCropActionConfig,
    VideoProcessorPadActionConfig,
    VideoProcessorFlipActionConfig,
    VideoProcessorRotateActionConfig,
    VideoProcessorSpeedActionConfig,
)

FFmpegVideoProcessorActionConfig = Annotated[
    Union[
        VideoProcessorResizeActionConfig,
        VideoProcessorCropActionConfig,
        VideoProcessorPadActionConfig,
        VideoProcessorFlipActionConfig,
        VideoProcessorRotateActionConfig,
        VideoProcessorSpeedActionConfig,
    ],
    Field(discriminator="method")
]
