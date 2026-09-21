from enum import Enum
from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import WorldMirrorImageTo3DModelActionConfig
from ..common import CommonImageTo3DModelComponentConfig
from .common import ImageTo3DModelFamily
from ....common import ModelDriverType

class WorldMirrorHead(str, Enum):
    CAMERA = "camera"
    DEPTH  = "depth"
    NORMAL = "normal"
    POINTS = "points"
    GS     = "gs"

class WorldMirrorImageTo3DModelComponentConfig(CommonImageTo3DModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageTo3DModelFamily.WORLD_MIRROR]
    subfolder: str = Field(default="HY-WorldMirror-2.0", description="Subfolder inside the model repository holding the WorldMirror checkpoint.")
    enable_bf16: bool = Field(default=False, description="Cast the model to bfloat16 for reduced VRAM at the cost of precision on non-critical layers.")
    disable_heads: List[WorldMirrorHead] = Field(default_factory=list, description="Prediction heads to disable and free from memory.")
    actions: List[WorldMirrorImageTo3DModelActionConfig] = Field(default_factory=list, description="Actions this image-to-3d component exposes to workflows.")
