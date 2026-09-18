from typing import Union, Annotated
from pydantic import Field
from .demucs import DemucsMusicSourceSeparationModelComponentConfig
from .mdx_net import MdxNetMusicSourceSeparationModelComponentConfig
from .roformer.bs_roformer import BsRoFormerMusicSourceSeparationModelComponentConfig
from .roformer.mel_band_roformer import MelBandRoFormerMusicSourceSeparationModelComponentConfig

CustomMusicSourceSeparationModelComponentConfig = Annotated[
    Union[
        DemucsMusicSourceSeparationModelComponentConfig,
        MdxNetMusicSourceSeparationModelComponentConfig,
        BsRoFormerMusicSourceSeparationModelComponentConfig,
        MelBandRoFormerMusicSourceSeparationModelComponentConfig,
    ],
    Field(discriminator="family")
]
