from typing import Union, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class ColorFormat(str, Enum):
    RGB = "rgb"
    BGR = "bgr"

class BlendMethod(str, Enum):
    LINEAR   = "linear"
    COSINE   = "cosine"
    GAUSSIAN = "gaussian"
    AVERAGE  = "average"

class CommonImageDeblurringParamsConfig(BaseModel):
    tile_size: Union[int, str] = Field(default=768, description="Tile size in pixels used to process large images; 0 disables tiling.")
    tile_overlap: Union[int, str] = Field(default=96, description="Overlap in pixels between adjacent tiles; must be smaller than `tile_size`.")
    blend: Union[BlendMethod, str] = Field(default=BlendMethod.LINEAR, description="Window function used to blend overlapping tiles.")
    augmented_inference: Union[bool, str] = Field(default=False, description="Average 8 flipped/rotated predictions (a.k.a. TTA); ~8x slower.")

class CommonImageDeblurringModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to deblur.")
    color_format: Union[ColorFormat, str] = Field(default=ColorFormat.RGB, description="Color channel order used by the model.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonImageDeblurringParamsConfig = Field(..., description="Backend-specific image deblurring parameters.")
