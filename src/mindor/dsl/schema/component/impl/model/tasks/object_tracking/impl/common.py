from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonObjectTrackingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.OBJECT_TRACKING]
