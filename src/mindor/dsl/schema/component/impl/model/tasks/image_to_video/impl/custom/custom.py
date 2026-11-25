from typing import Union, Annotated
from pydantic import Field
from .wan import WanImageToVideoModelComponentConfig
from .minimax_h3 import MinimaxH3ImageToVideoModelComponentConfig
from .pi_h3 import PiH3ImageToVideoModelComponentConfig

CustomImageToVideoModelComponentConfig = Annotated[
    Union[
        WanImageToVideoModelComponentConfig,
        MinimaxH3ImageToVideoModelComponentConfig,
        PiH3ImageToVideoModelComponentConfig,
    ],
    Field(discriminator="family")
]
