from typing import Union
from .pixal3d.pixal3d import Pixal3DImageTo3DModelActionConfig
from .pixal3d.pixal3d_mv import Pixal3DMultiViewImageTo3DModelActionConfig
from .anigen import AniGenImageTo3DModelActionConfig

CustomImageTo3DModelActionConfig = Union[
    Pixal3DImageTo3DModelActionConfig,
    Pixal3DMultiViewImageTo3DModelActionConfig,
    AniGenImageTo3DModelActionConfig,
]
