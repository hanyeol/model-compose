from typing import Union
from pydantic import Field
from ..common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class RealEsrganImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    denoise_strength: Union[float, str] = Field(default=0.5, description="Denoising strength, from 0.0 to 1.0.")
    tile_batch_size: Union[int, str] = Field(default=4, description="Number of tiles processed per batch.")
    tile_size: Union[int, str] = Field(default=192, description="Tile size in pixels used to process large images.")
    tile_pad_size: Union[int, str] = Field(default=24, description="Padding in pixels added around each tile to avoid seam artifacts.")
    pre_pad_size: Union[int, str] = Field(default=15, description="Padding in pixels added to the image before processing.")
    half_precision: Union[bool, str] = Field(default=False, description="Whether inference runs in FP16 half precision for speed.")

class RealEsrganImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: RealEsrganImageUpscaleParamsConfig = Field(default_factory=RealEsrganImageUpscaleParamsConfig)
