from typing import Union, Annotated
from pydantic import Field
from .impl.esrgan import EsrganImageUpscaleModelComponentConfig
from .impl.real_esrgan import RealEsrganImageUpscaleModelComponentConfig
from .impl.ldsr import LdsrImageUpscaleModelComponentConfig
from .impl.swinir import SwinIRImageUpscaleModelComponentConfig

CustomImageUpscaleModelComponentConfig = Annotated[
    Union[
        EsrganImageUpscaleModelComponentConfig,
        RealEsrganImageUpscaleModelComponentConfig,
        LdsrImageUpscaleModelComponentConfig,
        SwinIRImageUpscaleModelComponentConfig,
    ],
    Field(discriminator="family")
]
