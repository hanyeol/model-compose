from typing import Union, Annotated
from pydantic import Field
from .esrgan import EsrganImageUpscaleModelComponentConfig
from .real_esrgan import RealEsrganImageUpscaleModelComponentConfig
from .ldsr import LdsrImageUpscaleModelComponentConfig
from .swinir import SwinIRImageUpscaleModelComponentConfig

CustomImageUpscaleModelComponentConfig = Annotated[
    Union[
        EsrganImageUpscaleModelComponentConfig,
        RealEsrganImageUpscaleModelComponentConfig,
        LdsrImageUpscaleModelComponentConfig,
        SwinIRImageUpscaleModelComponentConfig,
    ],
    Field(discriminator="family")
]
