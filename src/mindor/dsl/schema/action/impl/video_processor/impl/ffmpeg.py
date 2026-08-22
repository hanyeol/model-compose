from typing import Union, Annotated
from pydantic import Field
from .common import (
    VideoProcessorResizeActionConfig,
    VideoProcessorCropActionConfig,
    VideoProcessorPadActionConfig,
    VideoProcessorFlipActionConfig,
    VideoProcessorRotateActionConfig,
)

FFmpegVideoProcessorActionConfig = Annotated[
    Union[
        VideoProcessorResizeActionConfig,
        VideoProcessorCropActionConfig,
        VideoProcessorPadActionConfig,
        VideoProcessorFlipActionConfig,
        VideoProcessorRotateActionConfig,
    ],
    Field(discriminator="method")
]
