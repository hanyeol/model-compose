from typing import Union, Annotated
from pydantic import Field
from .pixal3d import Pixal3DImageTo3DModelComponentConfig
from .anigen import AniGenImageTo3DModelComponentConfig

CustomImageTo3DModelComponentConfig = Annotated[
    Union[
        Pixal3DImageTo3DModelComponentConfig,
        AniGenImageTo3DModelComponentConfig,
    ],
    Field(discriminator="family")
]
