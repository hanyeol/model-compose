from typing import Union, Annotated
from pydantic import Field
from .pixal3d import Pixal3DImageTo3DModelComponentConfig

CustomImageTo3DModelComponentConfig = Annotated[
    Union[
        Pixal3DImageTo3DModelComponentConfig,
    ],
    Field(discriminator="family")
]
