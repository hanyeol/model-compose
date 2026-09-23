from typing import Union
from .impl import *

VideoToVideoModelActionConfig = Union[
    HuggingfaceVideoToVideoModelActionConfig,
    CustomVideoToVideoModelActionConfig,
]
