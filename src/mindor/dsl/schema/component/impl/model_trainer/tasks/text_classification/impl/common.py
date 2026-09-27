from typing import Literal
from ...common import CommonModelTrainerComponentConfig, ModelTrainerTaskType

class CommonTextClassificationModelTrainerComponentConfig(CommonModelTrainerComponentConfig):
    task: Literal[ModelTrainerTaskType.TEXT_CLASSIFICATION]
