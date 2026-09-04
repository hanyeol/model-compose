from typing import Union
from .esrgan import EsrganImageUpscaleModelActionConfig
from .real_esrgan import RealEsrganImageUpscaleModelActionConfig
from .ldsr import LdsrImageUpscaleModelActionConfig
from .swinir import SwinIRImageUpscaleModelActionConfig

CustomImageUpscaleModelActionConfig = Union[
    EsrganImageUpscaleModelActionConfig,
    RealEsrganImageUpscaleModelActionConfig,
    LdsrImageUpscaleModelActionConfig,
    SwinIRImageUpscaleModelActionConfig,
]
