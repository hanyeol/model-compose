from typing import Literal, Optional
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType, ModelConfig

class CommonFaceSwapModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_SWAP]
    model: Optional[ModelConfig] = Field(default=None, description="Model identifier — a HuggingFace repo ID or a local path; when omitted, the driver's default model is downloaded.")
