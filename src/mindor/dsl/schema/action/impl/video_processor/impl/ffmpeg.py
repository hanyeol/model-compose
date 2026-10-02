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
    VideoProcessorAdjustBrightnessActionConfig,
    VideoProcessorAdjustContrastActionConfig,
    VideoProcessorAdjustSaturationActionConfig,
    VideoProcessorAdjustGammaActionConfig,
    VideoProcessorAdjustHueActionConfig,
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
        VideoProcessorAdjustBrightnessActionConfig,
        VideoProcessorAdjustContrastActionConfig,
        VideoProcessorAdjustSaturationActionConfig,
        VideoProcessorAdjustGammaActionConfig,
        VideoProcessorAdjustHueActionConfig,
    ],
    Field(discriminator="method")
]
