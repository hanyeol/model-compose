from typing import Literal
from ...common import CommonModelTrainerComponentConfig, ModelTrainerTaskType

class CommonTypedDecisionModelTrainerComponentConfig(CommonModelTrainerComponentConfig):
    task: Literal[ModelTrainerTaskType.TYPED_DECISION]
