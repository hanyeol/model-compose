from typing import Literal, Optional
from pydantic import Field
from ...common import CommonImageTo3DModelComponentConfig
from .....common import ModelDriverType

class CommonPixal3DImageTo3DModelComponentConfig(CommonImageTo3DModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    low_vram: bool = Field(default=False, description="Load stage models on-demand to reduce peak VRAM at the cost of slower inference.")
    resolution: Optional[Literal[1024, 1536]] = Field(default=None, description="Pipeline resolution; defaults to 1024 when `low_vram` is set, else 1536.")
