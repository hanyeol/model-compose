from typing import Union
from .esrgan import EsrganImageUpscalingModelActionConfig
from .real_esrgan import RealEsrganImageUpscalingModelActionConfig
from .ldsr import LdsrImageUpscalingModelActionConfig
from .swinir import SwinIRImageUpscalingModelActionConfig

CustomImageUpscalingModelActionConfig = Union[
    EsrganImageUpscalingModelActionConfig,
    RealEsrganImageUpscalingModelActionConfig,
    LdsrImageUpscalingModelActionConfig,
    SwinIRImageUpscalingModelActionConfig,
]
