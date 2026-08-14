from typing import Literal, Optional
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonFaceTrackingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_TRACKING]
    version: Optional[str] = Field(default=None, description="Model version or variant identifier within the family.")
