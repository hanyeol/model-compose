from typing import Union, Optional
from pydantic import Field
from ..common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class LdsrImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    num_inference_steps: Union[int, str] = Field(default=100, description="Number of denoising steps run by the LDM super-resolution pipeline.")
    eta: Union[float, str] = Field(default=0.0, description="DDIM eta parameter; 0.0 is deterministic and 1.0 is fully stochastic.")
    downsample_method: Optional[str] = Field(default=None, description="Downsampling method applied to the image before upscaling.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation deterministic.")

class LdsrImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: LdsrImageUpscaleParamsConfig = Field(default_factory=LdsrImageUpscaleParamsConfig)
