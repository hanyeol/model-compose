from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonFaceEmotionClassificationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_EMOTION_CLASSIFICATION]
