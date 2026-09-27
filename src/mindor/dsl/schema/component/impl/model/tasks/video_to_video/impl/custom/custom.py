from typing import Union, Annotated
from pydantic import Field
from .wan import WanVideoToVideoModelComponentConfig

CustomVideoToVideoModelComponentConfig = Annotated[
    Union[
        WanVideoToVideoModelComponentConfig,
    ],
    Field(discriminator="family")
]
