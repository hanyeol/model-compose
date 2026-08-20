from typing import Union, Annotated
from pydantic import Field
from .impl.wan import WanImageToVideoModelComponentConfig

CustomImageToVideoModelComponentConfig = Annotated[
    Union[
        WanImageToVideoModelComponentConfig,
    ],
    Field(discriminator="family")
]
