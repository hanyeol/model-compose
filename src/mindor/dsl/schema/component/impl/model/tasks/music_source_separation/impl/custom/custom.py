from typing import Union, Annotated
from pydantic import Field
from .demucs import DemucsMusicSourceSeparationModelComponentConfig
from .mdx_net import MdxNetMusicSourceSeparationModelComponentConfig

CustomMusicSourceSeparationModelComponentConfig = Annotated[
    Union[
        DemucsMusicSourceSeparationModelComponentConfig,
        MdxNetMusicSourceSeparationModelComponentConfig,
    ],
    Field(discriminator="family")
]
