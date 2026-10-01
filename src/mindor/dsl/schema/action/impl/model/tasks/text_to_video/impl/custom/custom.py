from typing import Union
from .wan import WanTextToVideoModelActionConfig
from .minimax_h3 import MinimaxH3TextToVideoModelActionConfig

CustomTextToVideoModelActionConfig = Union[
    WanTextToVideoModelActionConfig,
    MinimaxH3TextToVideoModelActionConfig,
]
