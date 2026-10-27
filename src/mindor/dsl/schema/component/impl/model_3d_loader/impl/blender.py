from typing import Literal, Optional, Union, List
from pydantic import Field
from mindor.dsl.schema.action import BlenderModel3DLoaderActionConfig
from .common import CommonModel3DLoaderComponentConfig, Model3DLoaderDriverType

class BlenderModel3DLoaderComponentConfig(CommonModel3DLoaderComponentConfig):
    driver: Literal[Model3DLoaderDriverType.BLENDER]
    binary: Optional[str] = Field(default=None, description="Path to the blender executable; auto-discovered from PATH or standard install locations when omitted.")
    timeout: Union[float, str] = Field(default=120.0, description="Timeout in seconds for each blender subprocess.")
    actions: List[BlenderModel3DLoaderActionConfig] = Field(default_factory=list)
