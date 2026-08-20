from typing import Union, Optional
from pydantic import Field
from ...common import CommonImageToVideoParamsConfig, CommonImageToVideoModelActionConfig

class WanImageToVideoParamsConfig(CommonImageToVideoParamsConfig):
    inference_steps: Union[int, str] = Field(default=40, description="Number of diffusion inference steps.")
    guidance_scale: Union[float, str] = Field(default=5.0, description="Classifier-free guidance scale applied during sampling.")
    shift: Union[float, str] = Field(default=5.0, description="Flow-matching timestep shift applied to the scheduler.")

class WanImageToVideoModelActionConfig(CommonImageToVideoModelActionConfig):
    params: WanImageToVideoParamsConfig = Field(default_factory=WanImageToVideoParamsConfig, description="Wan image-to-video generation parameters.")
