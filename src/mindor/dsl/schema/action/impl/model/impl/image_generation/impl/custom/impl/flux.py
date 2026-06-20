from typing import Union, Optional
from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig

class FluxImageGenerationParamsConfig(BaseModel):
    num_inference_steps: Union[int, str] = Field(default=28, description="Number of denoising steps. Use 28 for FLUX.1-dev, 4 for FLUX.1-schnell.")
    guidance_scale: Union[float, str] = Field(default=3.5, description="Guidance scale. Use 3.5 for FLUX.1-dev, 0.0 for FLUX.1-schnell.")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    max_sequence_length: Union[int, str] = Field(default=512, description="Maximum sequence length for the T5 text encoder.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class FluxImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    params: FluxImageGenerationParamsConfig = Field(default_factory=FluxImageGenerationParamsConfig, description="Image generation configuration parameters.")
