from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class SpeechToTextModelArchitecture(str, Enum):
    WHISPER       = "whisper"
    WHISPER_LARGE = "whisper-large"

class SpeechToTextModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.SPEECH_TO_TEXT]
    architecture: SpeechToTextModelArchitecture = Field(..., description="Model architecture.")
    actions: List[SpeechToTextModelActionConfig] = Field(default_factory=list)
