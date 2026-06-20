from typing import Union, Optional
from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig

class HunyuanImageGenerationParamsConfig(BaseModel):
    negative_prompt: Optional[Union[str, list]] = Field(default=None, description="Negative prompt(s) describing what to avoid.")
    num_inference_steps: Union[int, str] = Field(default=50, description="Number of denoising steps.")
    distilled_guidance_scale: Union[float, str] = Field(default=3.25, description="Distilled guidance scale (Hunyuan-Image uses adaptive projected mix guidance).")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class HunyuanImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: HunyuanImageGenerationParamsConfig = Field(default_factory=HunyuanImageGenerationParamsConfig, description="Image generation configuration parameters.")
