from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeModel3DLoaderActionConfig
from .common import CommonModel3DLoaderComponentConfig, Model3DLoaderDriverType

class NativeModel3DLoaderComponentConfig(CommonModel3DLoaderComponentConfig):
    driver: Literal[Model3DLoaderDriverType.NATIVE]
    actions: List[NativeModel3DLoaderActionConfig] = Field(default_factory=list)
