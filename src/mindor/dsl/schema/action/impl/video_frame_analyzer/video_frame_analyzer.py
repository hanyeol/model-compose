from typing import Union
from .impl import *

VideoFrameAnalyzerActionConfig = Union[
    NativeVideoFrameAnalyzerActionConfig,
    OpenCvVideoFrameAnalyzerActionConfig,
]
