from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class ColorFormat(str, Enum):
    RGB = "rgb"
    BGR = "bgr"

class CommonImageUpscaleParamsConfig(BaseModel):
    color_format: ColorFormat = Field(default=ColorFormat.RGB, description="Color format for image processing.")

class CommonImageUpscaleModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image to upscale.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to process in a single batch.")
    params: CommonImageUpscaleParamsConfig = Field(..., description="Image upscale configuration parameters.")

class EsrganImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    tile_size: Union[int, str] = Field(default=0, description="Tile size for processing large images (0 = no tiling).")
    tile_pad_size: Union[int, str] = Field(default=10, description="Padding for tiles to avoid seam artifacts.")
    pre_pad_size: Union[int, str] = Field(default=0, description="Pre-padding before processing.")
    half_precision: Union[bool, str] = Field(default=False, description="Use half precision (FP16) for faster inference.")

class EsrganImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: EsrganImageUpscaleParamsConfig = Field(default_factory=EsrganImageUpscaleParamsConfig)

class RealEsrganImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    denoise_strength: Union[float, str] = Field(default=0.5, description="Denoising strength (0.0-1.0).")
    tile_batch_size: Union[int, str] = Field(default=4, description="Number of tiles to process in a single batch.")
    tile_size: Union[int, str] = Field(default=192, description="Tile size for large image processing.")
    tile_pad_size: Union[int, str] = Field(default=24, description="Tile padding size.")
    pre_pad_size: Union[int, str] = Field(default=15, description="Pre-padding size.")
    half_precision: Union[bool, str] = Field(default=False, description="Use half precision (FP16) for faster inference.")

class RealEsrganImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: RealEsrganImageUpscaleParamsConfig = Field(default_factory=RealEsrganImageUpscaleParamsConfig)

class LdsrImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    steps: Union[int, str] = Field(default=50, description="Number of diffusion steps.")
    eta: Union[float, str] = Field(default=1.0, description="DDIM eta parameter.")
    downsample_method: Optional[str] = Field(default=None, description="Downsampling method for preprocessing.")
    half_precision: Union[bool, str] = Field(default=False, description="Use half precision (FP16) for faster inference.")

class LdsrImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: LdsrImageUpscaleParamsConfig = Field(default_factory=LdsrImageUpscaleParamsConfig)

class SwinIRImageUpscaleParamsConfig(CommonImageUpscaleParamsConfig):
    task: Union[str, str] = Field(default="real_sr", description="SwinIR task type: real_sr, classical_sr, dn, etc.")
    tile: Union[int, str] = Field(default=None, description="Tile size for large image processing.")
    tile_overlap: Union[int, str] = Field(default=32, description="Overlap between tiles.")
    scale: Union[int, str] = Field(default=4, description="Upscaling factor.")
    window_size: Union[int, str] = Field(default=8, description="Window size for attention computation.")
    jpeg_quality: Union[int, str] = Field(default=40, description="JPEG quality for compression artifacts removal task.")

class SwinIRImageUpscaleModelActionConfig(CommonImageUpscaleModelActionConfig):
    params: SwinIRImageUpscaleParamsConfig = Field(default_factory=SwinIRImageUpscaleParamsConfig)

ImageUpscaleModelActionConfig = Union[
    EsrganImageUpscaleModelActionConfig,
    RealEsrganImageUpscaleModelActionConfig,
    LdsrImageUpscaleModelActionConfig,
    SwinIRImageUpscaleModelActionConfig,
]
