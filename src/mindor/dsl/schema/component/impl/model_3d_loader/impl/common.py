from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class Model3DLoaderDriverType(str, Enum):
    NATIVE  = "native"
    BLENDER = "blender"

class CommonModel3DLoaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_3D_LOADER]
    driver: Model3DLoaderDriverType = Field(..., description="Backend implementation used for 3D model loading.")
