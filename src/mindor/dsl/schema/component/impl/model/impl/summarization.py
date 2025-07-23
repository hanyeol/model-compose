from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import SummarizationModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class SummarizationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.SUMMARIZATION]
    actions: Dict[str, SummarizationModelActionConfig] = Field(default_factory=dict)
