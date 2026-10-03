from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

Model3DRendererComponentConfig = Annotated[
    Union[
        NativeModel3DRendererComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.MODEL_3D_RENDERER, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = Model3DRendererDriverType.NATIVE
