from typing import Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.action import ImageTo3DModelActionConfig
from ..common import CommonImageTo3DModelComponentConfig
from .common import ImageTo3DModelFamily
from ....common import ModelDriverType

class Pixal3DImageTo3DModelComponentConfig(CommonImageTo3DModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageTo3DModelFamily.PIXAL3D]
    low_vram: bool = Field(default=False, description="Load stage models on-demand to reduce peak VRAM at the cost of slower inference.")
    resolution: Optional[Literal[1024, 1536]] = Field(default=None, description="Pipeline resolution; defaults to 1024 when `low_vram` is set, else 1536.")
    actions: List[ImageTo3DModelActionConfig] = Field(default_factory=list, description="Actions this image-to-3d component exposes to workflows.")
