from typing import Union
from .impl import *

ImageCompressorActionConfig = Union[
    NativeImageCompressorActionConfig,
    OxipngImageCompressorActionConfig,
    PngquantImageCompressorActionConfig,
]
