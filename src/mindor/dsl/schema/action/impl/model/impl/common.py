from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class ModelTaskMode(str, Enum):
    INFERENCE = "inference"
    TRAINING  = "training"

class CommonModelActionConfig(CommonActionConfig):
    mode: ModelTaskMode = Field(default=ModelTaskMode.INFERENCE, description="")
