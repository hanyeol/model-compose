from typing import Union, Annotated
from pydantic import Field
from .esrgan import EsrganImageUpscalingModelComponentConfig
from .real_esrgan import RealEsrganImageUpscalingModelComponentConfig
from .ldsr import LdsrImageUpscalingModelComponentConfig
from .swinir import SwinIRImageUpscalingModelComponentConfig
from .hat import HatImageUpscalingModelComponentConfig

CustomImageUpscalingModelComponentConfig = Annotated[
    Union[
        EsrganImageUpscalingModelComponentConfig,
        RealEsrganImageUpscalingModelComponentConfig,
        LdsrImageUpscalingModelComponentConfig,
        SwinIRImageUpscalingModelComponentConfig,
        HatImageUpscalingModelComponentConfig,
    ],
    Field(discriminator="family")
]
