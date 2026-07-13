from typing import Union, Optional
from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig, CommonImageGenerationModelInpaintActionConfig

class CommonHuggingfaceImageGenerationParamsConfig(BaseModel):
    num_inference_steps: Union[int, str] = Field(default=30, description="Number of denoising steps.")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class CommonHuggingfaceImageGenerationInpaintParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    strength: Union[float, str] = Field(default=1.0, description="Noise strength for the input image.")

class CommonHuggingfaceImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: CommonHuggingfaceImageGenerationParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationParamsConfig, description="Image generation parameters.")

class CommonHuggingfaceImageGenerationModelInpaintActionConfig(CommonImageGenerationModelInpaintActionConfig):
    params: CommonHuggingfaceImageGenerationInpaintParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationInpaintParamsConfig, description="Image inpainting parameters.")
