from typing import Union
from .impl import *

ImageToTextModelActionConfig = Union[
    HuggingfaceImageToTextModelActionConfig,
    CustomImageToTextModelActionConfig,
]
