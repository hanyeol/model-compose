from typing import Union, Literal, Optional, List, Annotated
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
    clip_skip: Optional[Union[int, str]] = Field(default=None, description="Number of final CLIP text-encoder layers to skip; '2' matches common anime SD1.5 recipes.")

class SdxlHuggingfaceImageGenerationInpaintParamsConfig(CommonHuggingfaceImageGenerationInpaintParamsConfig):
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")
    clip_skip: Optional[Union[int, str]] = Field(default=None, description="Number of final CLIP text-encoder layers to skip; '2' matches common anime SD1.5 recipes.")

class SdxlHuggingfaceImageGenerationGenerateModelActionConfig(CommonHuggingfaceImageGenerationModelActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    negative_prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Negative prompt or prompts describing what to avoid.")
    params: SdxlHuggingfaceImageGenerationParamsConfig = Field(default_factory=SdxlHuggingfaceImageGenerationParamsConfig, description="SDXL-specific image generation parameters.")

class SdxlHuggingfaceImageGenerationModelInpaintActionConfig(CommonHuggingfaceImageGenerationModelInpaintActionConfig):
    method: Literal[ImageGenerationActionMethod.INPAINT] = Field(default=ImageGenerationActionMethod.INPAINT)
    negative_prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Negative prompt or prompts describing what to avoid.")
    params: SdxlHuggingfaceImageGenerationInpaintParamsConfig = Field(default_factory=SdxlHuggingfaceImageGenerationInpaintParamsConfig, description="SDXL-specific inpainting parameters.")

SdxlHuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        SdxlHuggingfaceImageGenerationGenerateModelActionConfig,
        SdxlHuggingfaceImageGenerationModelInpaintActionConfig,
    ],
    Field(discriminator="method")
]
