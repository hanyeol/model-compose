from __future__ import annotations

from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonImageProcessorActionConfig, ImageProcessorActionMethod

class OpenCvImageProcessorActionMethod(ImageProcessorActionMethod):
    CANNY = "canny"

class OpenCvImageProcessorCannyActionConfig(CommonImageProcessorActionConfig):
    method: Literal[OpenCvImageProcessorActionMethod.CANNY]
    low_threshold: Union[int, str] = Field(default=100, description="Lower hysteresis threshold for the gradient magnitude.")
    high_threshold: Union[int, str] = Field(default=200, description="Upper hysteresis threshold for the gradient magnitude.")

OpenCvImageProcessorActionConfig = Annotated[
    Union[
        OpenCvImageProcessorCannyActionConfig,
    ],
    Field(discriminator="method")
]
