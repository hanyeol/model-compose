from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class ImageProcessorActionMethod(str, Enum):
    RESIZE            = "resize"
    CROP              = "crop"
    ROTATE            = "rotate"
    FLIP              = "flip"
    GRAYSCALE         = "grayscale"
    BLUR              = "blur"
    SHARPEN           = "sharpen"
    ADJUST_BRIGHTNESS = "adjust-brightness"
    ADJUST_CONTRAST   = "adjust-contrast"
    ADJUST_SATURATION = "adjust-saturation"
    MERGE             = "merge"

class ImageScaleMode(str, Enum):
    FIT     = "fit"
    FILL    = "fill"
    STRETCH = "stretch"

class FlipDirection(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"

class ImageMergeMode(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"
    GRID       = "grid"
    OVERLAY    = "overlay"

class CommonImageProcessorActionConfig(CommonActionConfig):
    method: ImageProcessorActionMethod = Field(..., description="Image processor method.")
    image: Union[str, List[str]] = Field(..., description="Input image(s) (file path, base64 string, or variable reference).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images to process in a single batch.")
