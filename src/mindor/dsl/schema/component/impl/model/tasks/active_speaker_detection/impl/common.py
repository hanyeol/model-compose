from typing import Literal, Optional
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonActiveSpeakerDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.ACTIVE_SPEAKER_DETECTION]
    version: Optional[str] = Field(default=None, description="Model version or variant identifier within the family.")
