from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import InsightfaceFaceSwapModelActionConfig
from ...common import CommonFaceSwapModelComponentConfig
from .common import FaceSwapModelFamily
from .....common import ModelDriver

class InsightfaceFaceSwapModelComponentConfig(CommonFaceSwapModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceSwapModelFamily.INSIGHTFACE]
    detector_model: str = Field(default="buffalo_l", description="InsightFace face-analysis model pack used to detect and align faces (e.g. 'buffalo_l', 'antelopev2').")
    actions: List[InsightfaceFaceSwapModelActionConfig] = Field(default_factory=list)
