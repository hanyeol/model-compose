from typing import Union
from pydantic import Field
from ..common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class EsrganImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    tile_size: Union[int, str] = Field(default=0, description="Tile size for processing large images (0 = no tiling).")
    tile_pad_size: Union[int, str] = Field(default=10, description="Padding for tiles to avoid seam artifacts.")
    pre_pad_size: Union[int, str] = Field(default=0, description="Pre-padding before processing.")
    half_precision: Union[bool, str] = Field(default=False, description="Use half precision (FP16) for faster inference.")

class EsrganImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: EsrganImageUpscaleParamsConfig = Field(default_factory=EsrganImageUpscaleParamsConfig)
