from typing import Union, Annotated
from pydantic import Field
from .common import (
    ImageProcessorResizeActionConfig,
    ImageProcessorCropActionConfig,
    ImageProcessorRotateActionConfig,
    ImageProcessorFlipActionConfig,
    ImageProcessorGrayscaleActionConfig,
    ImageProcessorBlurActionConfig,
    ImageProcessorSharpenActionConfig,
    ImageProcessorAdjustBrightnessActionConfig,
    ImageProcessorAdjustContrastActionConfig,
    ImageProcessorAdjustSaturationActionConfig,
    ImageProcessorConcatActionConfig,
    ImageProcessorMergeActionConfig,
    ImageProcessorOverlayActionConfig,
    ImageProcessorMosaicActionConfig,
    ImageProcessorCompressActionConfig,
)

NativeImageProcessorActionConfig = Annotated[
    Union[
        ImageProcessorResizeActionConfig,
        ImageProcessorCropActionConfig,
        ImageProcessorRotateActionConfig,
        ImageProcessorFlipActionConfig,
        ImageProcessorGrayscaleActionConfig,
        ImageProcessorBlurActionConfig,
        ImageProcessorSharpenActionConfig,
        ImageProcessorAdjustBrightnessActionConfig,
        ImageProcessorAdjustContrastActionConfig,
        ImageProcessorAdjustSaturationActionConfig,
        ImageProcessorConcatActionConfig,
        ImageProcessorMergeActionConfig,
        ImageProcessorOverlayActionConfig,
        ImageProcessorMosaicActionConfig,
        ImageProcessorCompressActionConfig,
    ],
    Field(discriminator="method")
]
