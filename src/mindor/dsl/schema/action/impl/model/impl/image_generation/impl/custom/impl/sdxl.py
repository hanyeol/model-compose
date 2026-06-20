from typing import Union, Optional
from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig

class SdxlImageGenerationParamsConfig(BaseModel):
    negative_prompt: Optional[Union[str, list]] = Field(default=None, description="Negative prompt(s) describing what to avoid.")
    num_inference_steps: Union[int, str] = Field(default=30, description="Number of denoising steps.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class SdxlImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: SdxlImageGenerationParamsConfig = Field(default_factory=SdxlImageGenerationParamsConfig, description="Image generation configuration parameters.")
