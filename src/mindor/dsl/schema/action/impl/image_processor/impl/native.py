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
    ImageProcessorAdjustColorActionConfig,
    ImageProcessorAdjustBrightnessActionConfig,
    ImageProcessorAdjustContrastActionConfig,
    ImageProcessorAdjustSaturationActionConfig,
    ImageProcessorAdjustGammaActionConfig,
    ImageProcessorAdjustHueActionConfig,
    ImageProcessorConcatActionConfig,
    ImageProcessorMergeActionConfig,
    ImageProcessorOverlayActionConfig,
    ImageProcessorMosaicActionConfig,
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
        ImageProcessorAdjustColorActionConfig,
        ImageProcessorAdjustBrightnessActionConfig,
        ImageProcessorAdjustContrastActionConfig,
        ImageProcessorAdjustSaturationActionConfig,
        ImageProcessorAdjustGammaActionConfig,
        ImageProcessorAdjustHueActionConfig,
        ImageProcessorConcatActionConfig,
        ImageProcessorMergeActionConfig,
        ImageProcessorOverlayActionConfig,
        ImageProcessorMosaicActionConfig,
    ],
    Field(discriminator="method")
]
