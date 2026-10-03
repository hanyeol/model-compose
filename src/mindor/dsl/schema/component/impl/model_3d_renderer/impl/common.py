from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class Model3DRendererDriverType(str, Enum):
    NATIVE = "native"

class CommonModel3DRendererComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_3D_RENDERER]
    driver: Model3DRendererDriverType = Field(..., description="Backend implementation used for 3D model rendering.")
