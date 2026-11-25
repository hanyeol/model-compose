from typing import Union
from .wan import WanTextToVideoModelActionConfig
from .minimax_h3 import MinimaxH3TextToVideoModelActionConfig
from .pi_h3 import PiH3TextToVideoModelActionConfig

CustomTextToVideoModelActionConfig = Union[
    WanTextToVideoModelActionConfig,
    MinimaxH3TextToVideoModelActionConfig,
    PiH3TextToVideoModelActionConfig,
]
