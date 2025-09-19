from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class RealEsrganImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    denoise_strength: Union[float, str] = Field(default=0.5, description="Denoising strength (0.0-1.0).")
    tile_batch_size: Union[int, str] = Field(default=4, description="Number of tiles to process in a single batch.")
    tile_size: Union[int, str] = Field(default=192, description="Tile size for large image processing.")
    tile_pad_size: Union[int, str] = Field(default=24, description="Tile padding size.")
    pre_pad_size: Union[int, str] = Field(default=15, description="Pre-padding size.")
    half_precision: Union[bool, str] = Field(default=False, description="Use half precision (FP16) for faster inference.")

class RealEsrganImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: RealEsrganImageUpscaleParamsConfig = Field(default_factory=RealEsrganImageUpscaleParamsConfig)
