from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import Pixal3DMultiViewImageTo3DModelActionConfig
from ..common import ImageTo3DModelFamily
from .common import CommonPixal3DImageTo3DModelComponentConfig

class Pixal3DMultiViewImageTo3DModelComponentConfig(CommonPixal3DImageTo3DModelComponentConfig):
    family: Literal[ImageTo3DModelFamily.PIXAL3D_MV]
    actions: List[Pixal3DMultiViewImageTo3DModelActionConfig] = Field(default_factory=list, description="Actions this image-to-3d component exposes to workflows.")
