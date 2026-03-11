from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class AgentModelConfig(BaseModel):
    component: str = Field(..., description="ID of the component to use for LLM calls.")
    action: str = Field(default="__default__", description="ID of the action to invoke on the component.")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input mapping from agent internal state to component input. Supports variable interpolation.")

class AgentActionConfig(CommonActionConfig):
    model: AgentModelConfig = Field(..., description="LLM model configuration for this action.")
    system_prompt: Optional[Any] = Field(default=None, description="System prompt for the agent. Supports variable interpolation.")
    user_prompt: Optional[Any] = Field(default=None, description="User prompt for the agent. Supports variable interpolation.")
    max_iteration_count: Optional[int] = Field(default=None, description="Maximum number of ReAct loop iterations. Overrides component-level setting.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream messages as they are generated.")
