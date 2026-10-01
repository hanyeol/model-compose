from typing import Union, Annotated
from pydantic import Field
from .wan import WanTextToVideoModelComponentConfig
from .minimax_h3 import MinimaxH3TextToVideoModelComponentConfig

CustomTextToVideoModelComponentConfig = Annotated[
    Union[
        WanTextToVideoModelComponentConfig,
        MinimaxH3TextToVideoModelComponentConfig,
    ],
    Field(discriminator="family")
]
