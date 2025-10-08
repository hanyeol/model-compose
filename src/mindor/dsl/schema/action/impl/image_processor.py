from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class ImageProcessorActionMethod(str, Enum):
    RESIZE            = "resize"
    CROP              = "crop"
    ROTATE            = "rotate"
    FLIP              = "flip"
    GRAYSCALE         = "grayscale"
    BLUR              = "blur"
    SHARPEN           = "sharpen"
    ADJUST_BRIGHTNESS = "adjust-brightness"
    ADJUST_CONTRAST   = "adjust-contrast"
    ADJUST_SATURATION = "adjust-saturation"

class ImageScaleMode(str, Enum):
    FIT     = "fit"
    FILL    = "fill"
    STRETCH = "stretch"

class FlipDirection(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"

class CommonImageProcessorActionConfig(CommonActionConfig):
    method: ImageProcessorActionMethod = Field(..., description="Image processor method.")
    image: str = Field(..., description="Input image (file path, base64 string, or variable reference).")

class ImageProcessorResizeActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.RESIZE]
    width: Optional[Union[int, str]] = Field(None, description="Target width in pixels.")
    height: Optional[Union[int, str]] = Field(None, description="Target height in pixels.")
    scale_mode: Union[ImageScaleMode, str] = Field(ImageScaleMode.FIT, description="Resize mode.")

class ImageProcessorCropActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.CROP]
    x: Union[int, str] = Field(..., description="X coordinate of top-left corner.")
    y: Union[int, str] = Field(..., description="Y coordinate of top-left corner.")
    width: Union[int, str] = Field(..., description="Crop width in pixels.")
    height: Union[int, str] = Field(..., description="Crop height in pixels.")

class ImageProcessorRotateActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ROTATE]
    angle: Union[float, str] = Field(..., description="Rotation angle in degrees.")
    expand: Union[bool, str] = Field(True, description="Expand canvas to fit rotated image.")

class ImageProcessorFlipActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.FLIP]
    direction: Union[FlipDirection, str] = Field(..., description="Flip direction.")

class ImageProcessorGrayscaleActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.GRAYSCALE]

class ImageProcessorBlurActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.BLUR]
    radius: Union[float, str] = Field(defulat=2.0, description="Blur radius in pixels.")

class ImageProcessorSharpenActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.SHARPEN]
    factor: Union[float, str] = Field(default=1.0, description="Sharpening factor.")

class ImageProcessorAdjustBrightnessActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_BRIGHTNESS]
    factor: Union[float, str] = Field(..., description="Brightness factor.")

class ImageProcessorAdjustContrastActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_CONTRAST]
    factor: Union[float, str] = Field(..., description="Contrast factor.")

class ImageProcessorAdjustSaturationActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_SATURATION]
    factor: Union[float, str] = Field(..., description="Saturation factor.")

ImageProcessorActionConfig = Annotated[
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
        ImageProcessorAdjustSaturationActionConfig
    ],
    Field(discriminator="method")
]
