from typing import Union, Optional
from pydantic import Field
from .common import CommonHuggingfaceTextToImageModelActionConfig, CommonHuggingfaceTextToImageParamsConfig

class SdxlHuggingfaceTextToImageParamsConfig(CommonHuggingfaceTextToImageParamsConfig):
    negative_prompt: Optional[Union[str, list]] = Field(default=None, description="Negative prompt(s) describing what to avoid.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")

class SdxlHuggingfaceTextToImageModelActionConfig(CommonHuggingfaceTextToImageModelActionConfig):
    params: SdxlHuggingfaceTextToImageParamsConfig = Field(default_factory=SdxlHuggingfaceTextToImageParamsConfig, description="Image generation configuration parameters.")
