from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import Pixal3DImageTo3DModelActionConfig
from ..common import ImageTo3DModelFamily
from .common import CommonPixal3DImageTo3DModelComponentConfig

class Pixal3DImageTo3DModelComponentConfig(CommonPixal3DImageTo3DModelComponentConfig):
    family: Literal[ImageTo3DModelFamily.PIXAL3D]
    actions: List[Pixal3DImageTo3DModelActionConfig] = Field(default_factory=list, description="Actions this image-to-3d component exposes to workflows.")
