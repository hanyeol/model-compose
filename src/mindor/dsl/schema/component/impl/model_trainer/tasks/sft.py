from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import SftModelTrainerActionConfig
from .common import CommonModelTrainerComponentConfig, TrainingTaskType

class SftModelTrainerComponentConfig(CommonModelTrainerComponentConfig):
    task: Literal[TrainingTaskType.SFT]
    actions: List[SftModelTrainerActionConfig] = Field(default_factory=list)
