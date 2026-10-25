from enum import Enum
from typing import Union
from pydantic import Field
from ..common import CommonImageTo3DParamsConfig, CommonImageTo3DModelActionConfig

class TripoSplatOutputFormat(str, Enum):
    PLY   = "ply"
    SPLAT = "splat"

class TripoSplatImageTo3DParamsConfig(CommonImageTo3DParamsConfig):
    steps: Union[int, str] = Field(default=20, description="Flow-matching sampler steps.")
    guidance_scale: Union[float, str] = Field(default=3.0, description="Classifier-free guidance strength; <= 1.0 disables CFG.")
    shift: Union[float, str] = Field(default=3.0, description="Flow-matching timestep schedule shift; 1.0 is uniform.")
    num_gaussians: Union[int, str] = Field(default=262144, description="Target Gaussian count; 32768 to 262144, rounded to a multiple of 32.")
    erode_radius: Union[int, str] = Field(default=1, description="Alpha-matte erosion radius after background removal; 0 disables.")

class TripoSplatImageTo3DModelActionConfig(CommonImageTo3DModelActionConfig):
    format: Union[TripoSplatOutputFormat, str] = Field(default=TripoSplatOutputFormat.PLY, description="Output format: `ply` or `splat`.")
    params: TripoSplatImageTo3DParamsConfig = Field(default_factory=TripoSplatImageTo3DParamsConfig, description="TripoSplat generation parameters.")
