from typing import Union
from .wan import WanVideoToVideoModelActionConfig
from .minimax_h3 import MinimaxH3VideoToVideoModelActionConfig

CustomVideoToVideoModelActionConfig = Union[
    WanVideoToVideoModelActionConfig,
    MinimaxH3VideoToVideoModelActionConfig,
]
