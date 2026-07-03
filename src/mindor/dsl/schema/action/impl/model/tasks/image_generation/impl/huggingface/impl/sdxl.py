from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import ImageGenerationActionMethod
from .common import CommonHuggingfaceImageGenerationModelActionConfig, CommonHuggingfaceImageGenerationParamsConfig

class SdxlHuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    negative_prompt: Optional[Union[str, list]] = Field(default=None, description="Negative prompt(s) describing what to avoid.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")

class SdxlHuggingfaceImageGenerationGenerateModelActionConfig(CommonHuggingfaceImageGenerationModelActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    params: SdxlHuggingfaceImageGenerationParamsConfig = Field(default_factory=SdxlHuggingfaceImageGenerationParamsConfig, description="Image generation configuration parameters.")

SdxlHuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        SdxlHuggingfaceImageGenerationGenerateModelActionConfig,
    ],
    Field(discriminator="method")
]
