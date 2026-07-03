from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from .impl import *

ImageUpscaleModelActionConfig = Union[
    EsrganImageUpscaleModelActionConfig,
    RealEsrganImageUpscaleModelActionConfig,
    LdsrImageUpscaleModelActionConfig,
    SwinIRImageUpscaleModelActionConfig,
]
