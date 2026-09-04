from typing import Union
from pydantic import Field
from ..common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class EsrganImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    tile_size: Union[int, str] = Field(default=0, description="Tile size in pixels used to process large images; 0 disables tiling.")
    tile_pad_size: Union[int, str] = Field(default=10, description="Padding in pixels added around each tile to avoid seam artifacts.")
    pre_pad_size: Union[int, str] = Field(default=0, description="Padding in pixels added to the image before processing.")
    half_precision: Union[bool, str] = Field(default=False, description="Whether inference runs in FP16 half precision for speed.")

class EsrganImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: EsrganImageUpscaleParamsConfig = Field(default_factory=EsrganImageUpscaleParamsConfig)
