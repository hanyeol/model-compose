from typing import Union, Optional
from pydantic import Field
from .common import CommonHuggingfaceImageGenerationModelActionConfig, CommonHuggingfaceImageGenerationParamsConfig

class SdxlHuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    negative_prompt: Optional[Union[str, list]] = Field(default=None, description="Negative prompt(s) describing what to avoid.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")

class SdxlHuggingfaceImageGenerationModelActionConfig(CommonHuggingfaceImageGenerationModelActionConfig):
    params: SdxlHuggingfaceImageGenerationParamsConfig = Field(default_factory=SdxlHuggingfaceImageGenerationParamsConfig, description="Image generation configuration parameters.")
