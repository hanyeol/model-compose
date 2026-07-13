from typing import Union, Optional
from pydantic import Field
from ...common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class LdsrImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    num_inference_steps: Union[int, str] = Field(default=100, description="Number of denoising steps for the LDM super-resolution pipeline.")
    eta: Union[float, str] = Field(default=0.0, description="DDIM eta parameter (0.0 = deterministic, 1.0 = full stochasticity).")
    downsample_method: Optional[str] = Field(default=None, description="Downsampling method applied before upscaling.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class LdsrImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: LdsrImageUpscaleParamsConfig = Field(default_factory=LdsrImageUpscaleParamsConfig)
