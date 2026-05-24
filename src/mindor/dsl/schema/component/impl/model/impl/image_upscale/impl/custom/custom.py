from typing import Union, Annotated
from enum import Enum
from pydantic import Field

class CustomImageUpscaleModelFamily(str, Enum):
    ESRGAN      = "esrgan"
    REAL_ESRGAN = "real-esrgan"
    LDSR        = "ldsr"
    SWINIR      = "swinir"

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
