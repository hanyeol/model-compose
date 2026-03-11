from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import AgentActionConfig
from .common import ComponentType, CommonComponentConfig

class AgentComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AGENT]
    tools: List[str] = Field(default_factory=list, description="List of workflow IDs to use as tools.")
    max_iteration_count: int = Field(default=10, description="Maximum number of ReAct loop iterations.")
    actions: List[AgentActionConfig] = Field(default_factory=list)
