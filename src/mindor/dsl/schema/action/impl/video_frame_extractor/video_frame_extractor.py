from typing import Union
from .impl import *

VideoFrameExtractorActionConfig = Union[
    FFmpegVideoFrameExtractorActionConfig,
    OpencvVideoFrameExtractorActionConfig,
]
