from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import AgentActionConfig, AgentModelConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from .common import ComponentType, CommonComponentConfig

class AgentComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AGENT]
    model: AgentModelConfig = Field(..., description="LLM model configuration for this agent.")
    instructions: Optional[str] = Field(default=None, description="Agent's behavioral guidelines and identity, applied as a system message.")
    tools: List[Union[str, ModelTool]] = Field(default_factory=list, description="List of Workflow ID or tool schema.")
    max_iteration_count: int = Field(default=10, description="Maximum number of ReAct loop iterations.")
    actions: List[AgentActionConfig] = Field(default_factory=list)
