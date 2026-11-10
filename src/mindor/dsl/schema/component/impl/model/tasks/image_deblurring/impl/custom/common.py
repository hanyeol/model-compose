from typing import Literal
from enum import Enum

class ImageDeblurringModelFamily(str, Enum):
    HI_DIFF     = "hi-diff"
    MISC_FILTER = "misc-filter"

ImageDeblurringVariant = Literal[ "RealBlur_J", "RealBlur_R", "GoPro" ]
