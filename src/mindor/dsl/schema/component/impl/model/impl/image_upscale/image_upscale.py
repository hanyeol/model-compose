from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

ImageUpscaleModelComponentConfig = Annotated[
    Union[ 
        EsrganImageUpscaleModelComponentConfig,
        RealEsrganImageUpscaleModelComponentConfig,
        LdsrImageUpscaleModelComponentConfig,
        SwinIRImageUpscaleModelComponentConfig,
    ],
    Field(discriminator="architecture")
]
