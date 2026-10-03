from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import Model3DRendererActionConfig
from .common import CommonModel3DRendererComponentConfig, Model3DRendererDriverType

class NativeModel3DRendererComponentConfig(CommonModel3DRendererComponentConfig):
    driver: Literal[Model3DRendererDriverType.NATIVE]
    actions: List[Model3DRendererActionConfig] = Field(default_factory=list)
