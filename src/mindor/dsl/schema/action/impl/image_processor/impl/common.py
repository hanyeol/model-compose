from __future__ import annotations

from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class ImageProcessorActionMethod(str, Enum):
    """Base enum shared by every image-processor driver's method set.

    Intentionally empty: Python enums with members can't be subclassed, so
    each driver (native, opencv, ...) extends this blank base to declare
    its own methods while keeping a common parent type for schema wiring.
    """
    pass

class ImageScaleMode(str, Enum):
    FIT     = "fit"
    FILL    = "fill"
    STRETCH = "stretch"

class FlipDirection(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"

class ImageConcatMode(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"
    GRID       = "grid"

class ImagePositionAnchor(str, Enum):
    TOP_LEFT      = "top-left"
    TOP_CENTER    = "top-center"
    TOP_RIGHT     = "top-right"
    CENTER_LEFT   = "center-left"
    CENTER        = "center"
    CENTER_RIGHT  = "center-right"
    BOTTOM_LEFT   = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT  = "bottom-right"

class CommonImageProcessorActionConfig(CommonActionConfig):
    method: ImageProcessorActionMethod = Field(..., description="Image processing operation this action performs.")
    image: Union[str, List[str]] = Field(..., description="Input image or list of images.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images processed per batch.")
