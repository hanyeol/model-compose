from typing import Union
from .esrgan import EsrganImageUpscalingModelActionConfig
from .real_esrgan import RealEsrganImageUpscalingModelActionConfig
from .ldsr import LdsrImageUpscalingModelActionConfig
from .swinir import SwinIRImageUpscalingModelActionConfig
from .hat import HatImageUpscalingModelActionConfig

CustomImageUpscalingModelActionConfig = Union[
    EsrganImageUpscalingModelActionConfig,
    RealEsrganImageUpscalingModelActionConfig,
    LdsrImageUpscalingModelActionConfig,
    SwinIRImageUpscalingModelActionConfig,
    HatImageUpscalingModelActionConfig,
]
