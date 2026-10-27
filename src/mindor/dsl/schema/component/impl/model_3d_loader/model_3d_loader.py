from typing import Union, Annotated, Dict, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

Model3DLoaderComponentConfig = Annotated[
    Union[
        NativeModel3DLoaderComponentConfig,
        BlenderModel3DLoaderComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.MODEL_3D_LOADER, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = Model3DLoaderDriverType.NATIVE
