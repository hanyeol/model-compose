from typing import Union
from .pixal3d import Pixal3DImageTo3DModelActionConfig
from .anigen import AniGenImageTo3DModelActionConfig

CustomImageTo3DModelActionConfig = Union[
    Pixal3DImageTo3DModelActionConfig,
    AniGenImageTo3DModelActionConfig,
]
