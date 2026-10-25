from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TripoSplatImageTo3DModelActionConfig
from ..common import CommonImageTo3DModelComponentConfig
from .common import ImageTo3DModelFamily
from ....common import ModelDriverType

class TripoSplatImageTo3DModelComponentConfig(CommonImageTo3DModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageTo3DModelFamily.TRIPOSPLAT]
    actions: List[TripoSplatImageTo3DModelActionConfig] = Field(default_factory=list, description="Actions this image-to-3d component exposes to workflows.")
