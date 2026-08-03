from typing import Union, Optional
from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig, CommonImageGenerationModelInpaintActionConfig

class CommonHuggingfaceImageGenerationParamsConfig(BaseModel):
    num_inference_steps: Union[int, str] = Field(default=30, description="Number of denoising steps.")

class CommonHuggingfaceImageGenerationInpaintParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    strength: Union[float, str] = Field(default=1.0, description="Noise strength for the input image.")

class CommonHuggingfaceImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: CommonHuggingfaceImageGenerationParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationParamsConfig, description="Image generation parameters.")

class CommonHuggingfaceImageGenerationModelInpaintActionConfig(CommonImageGenerationModelInpaintActionConfig):
    params: CommonHuggingfaceImageGenerationInpaintParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationInpaintParamsConfig, description="Image inpainting parameters.")
