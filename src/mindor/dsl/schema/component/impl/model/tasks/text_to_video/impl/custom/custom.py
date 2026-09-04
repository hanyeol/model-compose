from typing import Union, Annotated
from pydantic import Field
from .wan import WanTextToVideoModelComponentConfig

CustomTextToVideoModelComponentConfig = Annotated[
    Union[
        WanTextToVideoModelComponentConfig,
    ],
    Field(discriminator="family")
]
