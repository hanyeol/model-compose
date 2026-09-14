from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonLipSyncModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.LIP_SYNC]
