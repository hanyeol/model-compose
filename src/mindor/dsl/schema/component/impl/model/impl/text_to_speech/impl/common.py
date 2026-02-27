from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Type, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelComponentConfig, ModelTaskType, ModelDriver

class TextToSpeechModelFamily(str, Enum):
    QWEN = "qwen"

class CommonTextToSpeechModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_TO_SPEECH]
    driver: ModelDriver = Field(default=ModelDriver.CUSTOM)
    family: TextToSpeechModelFamily = Field(..., description="Model family.")
