from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class SwinIRImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    task: Union[str, str] = Field(default="real_sr", description="SwinIR task type: real_sr, classical_sr, dn, etc.")
    tile: Union[int, str] = Field(default=None, description="Tile size for large image processing.")
    tile_overlap: Union[int, str] = Field(default=32, description="Overlap between tiles.")
    scale: Union[int, str] = Field(default=4, description="Upscaling factor.")
    window_size: Union[int, str] = Field(default=8, description="Window size for attention computation.")
    jpeg_quality: Union[int, str] = Field(default=40, description="JPEG quality for compression artifacts removal task.")

class SwinIRImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: SwinIRImageUpscaleParamsConfig = Field(default_factory=SwinIRImageUpscaleParamsConfig)
