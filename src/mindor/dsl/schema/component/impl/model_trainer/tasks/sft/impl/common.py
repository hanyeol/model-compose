from typing import Literal
from ...common import CommonModelTrainerComponentConfig, ModelTrainerTaskType

class CommonSftModelTrainerComponentConfig(CommonModelTrainerComponentConfig):
    task: Literal[ModelTrainerTaskType.SFT]
