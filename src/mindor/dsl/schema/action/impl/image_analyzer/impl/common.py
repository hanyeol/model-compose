from typing import Union, Literal, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class ImageAnalyzerMetric(str, Enum):
    BRIGHTNESS = "brightness"
    CONTRAST   = "contrast"
    SHARPNESS  = "sharpness"
    EXPOSURE   = "exposure"

class CommonImageAnalyzerActionConfig(CommonActionConfig):
    metric: ImageAnalyzerMetric = Field(..., description="Kind of measurement performed on the image.")
    image: Union[str, List[str]] = Field(..., description="Image source or list of sources to analyze.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images processed per batch.")

class BrightnessImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[ImageAnalyzerMetric.BRIGHTNESS]

class ContrastImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[ImageAnalyzerMetric.CONTRAST]

class SharpnessImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[ImageAnalyzerMetric.SHARPNESS]
    blur_threshold: Union[float, int, str] = Field(default=100.0, description="Laplacian variance below which the image is flagged as blurry.")

class ExposureImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[ImageAnalyzerMetric.EXPOSURE]
    shadow_threshold: Union[int, str] = Field(default=16, description="Pixel value (0-255) below which a pixel counts as clipped-shadow.")
    highlight_threshold: Union[int, str] = Field(default=239, description="Pixel value (0-255) above which a pixel counts as clipped-highlight.")
