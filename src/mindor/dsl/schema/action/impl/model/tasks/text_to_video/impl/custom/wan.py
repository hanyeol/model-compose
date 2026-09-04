from typing import Union, Optional
from pydantic import Field
from ..common import CommonTextToVideoParamsConfig, CommonTextToVideoModelActionConfig

class WanTextToVideoParamsConfig(CommonTextToVideoParamsConfig):
    inference_steps: Union[int, str] = Field(default=50, description="Number of diffusion inference steps.")
    guidance_scale: Union[float, str] = Field(default=5.0, description="Classifier-free guidance scale applied during sampling.")
    shift: Union[float, str] = Field(default=5.0, description="Flow-matching timestep shift applied to the scheduler.")

class WanTextToVideoModelActionConfig(CommonTextToVideoModelActionConfig):
    params: WanTextToVideoParamsConfig = Field(default_factory=WanTextToVideoParamsConfig, description="Wan text-to-video generation parameters.")
