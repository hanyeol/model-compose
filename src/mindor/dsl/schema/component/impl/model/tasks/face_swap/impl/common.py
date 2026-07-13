from typing import Literal, Optional, Union
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType, ModelConfig

class CommonFaceSwapModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_SWAP]
    model: Optional[Union[str, ModelConfig]] = Field(default=None, description="Model source configuration. When omitted, the driver's default model is downloaded.")
