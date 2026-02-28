from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import LanguageModelComponentConfig, ModelTaskType

class TextGenerationModelArchitecture(str, Enum):
    CAUSAL  = "causal"
    SEQ2SEQ = "seq2seq"

class TextGenerationModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_GENERATION]
    architecture: TextGenerationModelArchitecture = Field(default=TextGenerationModelArchitecture.CAUSAL, description="Model architecture.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
