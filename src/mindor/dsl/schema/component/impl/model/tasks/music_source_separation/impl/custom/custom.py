from typing import Union, Annotated
from pydantic import Field
from .impl.demucs import DemucsMusicSourceSeparationModelComponentConfig
from .impl.mdx_net import MdxNetMusicSourceSeparationModelComponentConfig

CustomMusicSourceSeparationModelComponentConfig = Annotated[
    Union[
        DemucsMusicSourceSeparationModelComponentConfig,
        MdxNetMusicSourceSeparationModelComponentConfig,
    ],
    Field(discriminator="family")
]
