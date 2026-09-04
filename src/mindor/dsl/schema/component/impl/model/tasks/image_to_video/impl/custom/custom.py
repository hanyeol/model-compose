from typing import Union, Annotated
from pydantic import Field
from .wan import WanImageToVideoModelComponentConfig

CustomImageToVideoModelComponentConfig = Annotated[
    Union[
        WanImageToVideoModelComponentConfig,
    ],
    Field(discriminator="family")
]
