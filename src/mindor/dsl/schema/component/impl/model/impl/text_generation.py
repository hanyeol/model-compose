from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class TextGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_GENERATION]
    actions: Dict[str, TextGenerationModelActionConfig] = Field(default_factory=dict)
