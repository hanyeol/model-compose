from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class LdsrImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    steps: Union[int, str] = Field(default=50, description="Number of diffusion steps.")
    eta: Union[float, str] = Field(default=1.0, description="DDIM eta parameter.")
    downsample_method: Optional[str] = Field(default=None, description="Downsampling method for preprocessing.")
    half_precision: Union[bool, str] = Field(default=False, description="Use half precision (FP16) for faster inference.")

class LdsrImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: LdsrImageUpscaleParamsConfig = Field(default_factory=LdsrImageUpscaleParamsConfig)
