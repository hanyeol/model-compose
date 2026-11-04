from typing import Union
from .wan import WanImageToVideoModelActionConfig
from .minimax_h3 import MinimaxH3ImageToVideoModelActionConfig

CustomImageToVideoModelActionConfig = Union[
    WanImageToVideoModelActionConfig,
    MinimaxH3ImageToVideoModelActionConfig,
]
