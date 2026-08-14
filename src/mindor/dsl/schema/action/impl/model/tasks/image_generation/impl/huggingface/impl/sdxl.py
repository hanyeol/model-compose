from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import ImageGenerationActionMethod
from .common import (
    CommonHuggingfaceImageGenerationModelActionConfig,
    CommonHuggingfaceImageGenerationModelInpaintActionConfig,
    CommonHuggingfaceImageGenerationParamsConfig,
    CommonHuggingfaceImageGenerationInpaintParamsConfig,
)

class SdxlHuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")

class SdxlHuggingfaceImageGenerationInpaintParamsConfig(CommonHuggingfaceImageGenerationInpaintParamsConfig):
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")

class SdxlHuggingfaceImageGenerationGenerateModelActionConfig(CommonHuggingfaceImageGenerationModelActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    params: SdxlHuggingfaceImageGenerationParamsConfig = Field(default_factory=SdxlHuggingfaceImageGenerationParamsConfig, description="SDXL-specific image generation parameters.")

class SdxlHuggingfaceImageGenerationModelInpaintActionConfig(CommonHuggingfaceImageGenerationModelInpaintActionConfig):
    method: Literal[ImageGenerationActionMethod.INPAINT] = Field(default=ImageGenerationActionMethod.INPAINT)
    params: SdxlHuggingfaceImageGenerationInpaintParamsConfig = Field(default_factory=SdxlHuggingfaceImageGenerationInpaintParamsConfig, description="SDXL-specific inpainting parameters.")

SdxlHuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        SdxlHuggingfaceImageGenerationGenerateModelActionConfig,
        SdxlHuggingfaceImageGenerationModelInpaintActionConfig,
    ],
    Field(discriminator="method")
]
