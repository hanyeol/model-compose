from typing import Union, Annotated
from pydantic import Field
from .virtuoso_net import VirtuosoNetMusicPerformanceModelComponentConfig

CustomMusicPerformanceModelComponentConfig = Annotated[
    Union[
        VirtuosoNetMusicPerformanceModelComponentConfig,
    ],
    Field(discriminator="family")
]
