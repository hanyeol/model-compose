from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextToSpeechModelActionConfig
from .common import CommonTextToSpeechModelComponentConfig, TextToSpeechModelFamily

class QwenTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    family: Literal[TextToSpeechModelFamily.QWEN]
    actions: List[TextToSpeechModelActionConfig] = Field(default_factory=list)
