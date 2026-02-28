from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import WorkflowActionConfig
from .common import ComponentType, CommonComponentConfig

class WorkflowComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WORKFLOW]
    actions: List[WorkflowActionConfig] = Field(default_factory=list)
