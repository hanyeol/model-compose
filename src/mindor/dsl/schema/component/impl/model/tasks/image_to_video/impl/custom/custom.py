from typing import Union, Annotated
from pydantic import Field
from .wan import WanImageToVideoModelComponentConfig
from .minimax_h3 import MinimaxH3ImageToVideoModelComponentConfig

CustomImageToVideoModelComponentConfig = Annotated[
    Union[
        WanImageToVideoModelComponentConfig,
        MinimaxH3ImageToVideoModelComponentConfig,
    ],
    Field(discriminator="family")
]
