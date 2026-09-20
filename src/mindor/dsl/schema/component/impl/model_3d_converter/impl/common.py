from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class Model3DConverterDriverType(str, Enum):
    NATIVE = "native"

class CommonModel3DConverterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_3D_CONVERTER]
    driver: Model3DConverterDriverType = Field(..., description="Backend implementation used for 3D model conversion.")
