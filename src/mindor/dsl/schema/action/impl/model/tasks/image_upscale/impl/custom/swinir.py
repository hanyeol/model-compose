from typing import Union
from pydantic import Field
from ..common import CommonImageUpscaleModelActionConfig, CommonImageUpscaleParamsConfig

class SwinIRImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    task: str = Field(default="real_sr", description="SwinIR task variant (e.g., real_sr, classical_sr, dn).")
    tile_size: Union[int, str] = Field(default=None, description="Tile size in pixels used to process large images.")
    tile_overlap: Union[int, str] = Field(default=32, description="Overlap in pixels between adjacent tiles.")
    scale: Union[int, str] = Field(default=4, description="Upscaling factor applied to the output.")
    window_size: Union[int, str] = Field(default=8, description="Attention window size used by the SwinIR model.")
    jpeg_quality: Union[int, str] = Field(default=40, description="JPEG quality assumed by the compression-artifact-removal task.")

class SwinIRImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: SwinIRImageUpscaleParamsConfig = Field(default_factory=SwinIRImageUpscaleParamsConfig)
