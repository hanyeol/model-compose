from enum import Enum
from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageTo3DModelActionConfig
from ..common import CommonImageTo3DModelComponentConfig
from .common import ImageTo3DModelFamily
from ....common import ModelDriverType

class AniGenSSVariant(str, Enum):
    SOLO = "solo"
    EPIC = "epic"
    DUET = "duet"

class AniGenSLATVariant(str, Enum):
    AUTO    = "auto"
    CONTROL = "control"

class AniGenImageTo3DModelComponentConfig(CommonImageTo3DModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageTo3DModelFamily.ANIGEN]
    ss_variant: AniGenSSVariant = Field(default=AniGenSSVariant.SOLO, description="SS-Flow checkpoint variant (solo/epic/duet).")
    slat_variant: AniGenSLATVariant = Field(default=AniGenSLATVariant.AUTO, description="SLAT-Flow checkpoint variant (auto/control).")
    actions: List[ImageTo3DModelActionConfig] = Field(default_factory=list, description="Actions this image-to-3d component exposes to workflows.")
