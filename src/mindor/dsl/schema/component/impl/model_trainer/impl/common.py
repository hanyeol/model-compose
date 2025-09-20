from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType

class TrainingTaskType(str, Enum):
    SFT            = "sft"
    CLASSIFICATION = "classification"

class TrainingAdapterType(str, Enum):
    LORA  = "lora"
    QLORA = "qlora"

class CommonModelTrainerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_TRAINER]
    task: TrainingTaskType = Field(..., description="Type of training task to perform.")
    adapter: Optional[TrainingAdapterType] = Field(default=None, description="Parameter-efficient adapter method to use.")
