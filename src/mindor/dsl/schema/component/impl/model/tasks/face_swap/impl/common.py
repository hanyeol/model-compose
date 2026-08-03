from typing import Literal, Optional
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType, ModelConfig

class CommonFaceSwapModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_SWAP]
    model: Optional[ModelConfig] = Field(default=None, description="Model repository or local file path. If omitted, downloads the driver's default model.")
