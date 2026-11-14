from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class ImageAnalyzerMetric(str, Enum):
    """Base enum shared by every image-analyzer driver's metric set.

    Intentionally empty: Python enums with members can't be subclassed, so
    each driver (native, opencv, ...) extends this blank base to declare
    its own metrics while keeping a common parent type for schema wiring.
    """
    pass

class CommonImageAnalyzerActionConfig(CommonActionConfig):
    metric: ImageAnalyzerMetric = Field(..., description="Kind of measurement performed on the image.")
    image: Union[str, List[str]] = Field(..., description="Image source or list of sources to analyze.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images processed per batch.")
