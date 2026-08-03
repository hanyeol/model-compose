from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonFaceDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_DETECTION]
