from typing import Union
from .impl import *

MediaInspectorActionConfig = Union[
    FFmpegMediaInspectorActionConfig,
    ExiftoolMediaInspectorActionConfig,
]
