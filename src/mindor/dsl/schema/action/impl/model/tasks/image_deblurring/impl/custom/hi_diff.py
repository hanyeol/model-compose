from typing import Optional, Union
from pydantic import Field
from ..common import CommonImageDeblurringModelActionConfig, CommonImageDeblurringParamsConfig

class HiDiffImageDeblurringParamsConfig(CommonImageDeblurringParamsConfig):
    steps: Union[int, str] = Field(default=0, description="Diffusion sampling steps; 0 picks the per-variant default (16 for RealBlur, 8 for GoPro).")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for the diffusion prior; None picks a fresh seed each run.")

class HiDiffImageDeblurringModelActionConfig(CommonImageDeblurringModelActionConfig):
    params: HiDiffImageDeblurringParamsConfig = Field(default_factory=HiDiffImageDeblurringParamsConfig)
