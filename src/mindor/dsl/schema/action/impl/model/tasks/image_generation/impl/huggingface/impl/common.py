from typing import Union, Optional
from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig, CommonImageGenerationModelInpaintActionConfig

class CommonHuggingfaceImageGenerationParamsConfig(BaseModel):
    num_inference_steps: Union[int, str] = Field(default=30, description="Number of denoising steps run during sampling.")

class CommonHuggingfaceImageGenerationInpaintParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    strength: Union[float, str] = Field(default=1.0, description="Noise strength applied to the input image before denoising.")

class CommonHuggingfaceImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: CommonHuggingfaceImageGenerationParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationParamsConfig, description="Sampling parameters used for image generation.")

class CommonHuggingfaceImageGenerationModelInpaintActionConfig(CommonImageGenerationModelInpaintActionConfig):
    params: CommonHuggingfaceImageGenerationInpaintParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationInpaintParamsConfig, description="Sampling parameters used for image inpainting.")
