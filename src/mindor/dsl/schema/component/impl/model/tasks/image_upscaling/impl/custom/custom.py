from typing import Union, Annotated
from pydantic import Field
from .esrgan import EsrganImageUpscalingModelComponentConfig
from .real_esrgan import RealEsrganImageUpscalingModelComponentConfig
from .ldsr import LdsrImageUpscalingModelComponentConfig
from .swinir import SwinIRImageUpscalingModelComponentConfig

CustomImageUpscalingModelComponentConfig = Annotated[
    Union[
        EsrganImageUpscalingModelComponentConfig,
        RealEsrganImageUpscalingModelComponentConfig,
        LdsrImageUpscalingModelComponentConfig,
        SwinIRImageUpscalingModelComponentConfig,
    ],
    Field(discriminator="family")
]
