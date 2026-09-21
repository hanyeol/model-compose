from typing import Union, Annotated
from pydantic import Field
from .pixal3d.pixal3d import Pixal3DImageTo3DModelComponentConfig
from .pixal3d.pixal3d_mv import Pixal3DMultiViewImageTo3DModelComponentConfig
from .anigen import AniGenImageTo3DModelComponentConfig
from .world_mirror import WorldMirrorImageTo3DModelComponentConfig

CustomImageTo3DModelComponentConfig = Annotated[
    Union[
        Pixal3DImageTo3DModelComponentConfig,
        Pixal3DMultiViewImageTo3DModelComponentConfig,
        AniGenImageTo3DModelComponentConfig,
        WorldMirrorImageTo3DModelComponentConfig,
    ],
    Field(discriminator="family")
]
