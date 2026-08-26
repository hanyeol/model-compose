from typing import Union
from .impl import *

SubtitleLoaderActionConfig = Union[
    LocalSubtitleLoaderActionConfig,
    YtdlpSubtitleLoaderActionConfig,
]
