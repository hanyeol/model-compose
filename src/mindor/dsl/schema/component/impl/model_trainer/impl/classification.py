from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ClassificationModelTrainerActionConfig
from .common import CommonModelTrainerComponentConfig, TrainingTaskType

class ClassificationModelTrainerComponentConfig(CommonModelTrainerComponentConfig):
    task: Literal[TrainingTaskType.CLASSIFICATION]
    actions: List[ClassificationModelTrainerActionConfig] = Field(default_factory=list)
