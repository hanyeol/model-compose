from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import Model3DConverterActionConfig
from .common import CommonModel3DConverterComponentConfig, Model3DConverterDriverType

class NativeModel3DConverterComponentConfig(CommonModel3DConverterComponentConfig):
    driver: Literal[Model3DConverterDriverType.NATIVE]
    actions: List[Model3DConverterActionConfig] = Field(default_factory=list)
