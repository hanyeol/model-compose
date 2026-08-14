from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import AgentActionConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from .common import ComponentType, CommonComponentConfig

class AgentModelConfig(BaseModel):
    component: str = Field(..., description="ID of the component that handles LLM calls for this agent.")
    action: str = Field(default="__default__", description="ID of the action invoked on the component.")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input mapping from the agent's internal state to the component's input fields.")
    output: Optional[Any] = Field(default=None, description="Output mapping that shapes the component's response into a chat-completion message.")

class AgentComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AGENT]
    model: AgentModelConfig = Field(..., description="LLM backend the agent uses for reasoning and tool calls.")
    instructions: Optional[str] = Field(default=None, description="System-message text that sets the agent's persona and behavior.")
    tools: List[Union[str, ModelTool]] = Field(default_factory=list, description="Workflow IDs or tool schemas the agent may call.")
    max_iteration_count: int = Field(default=32, description="Maximum number of reasoning-and-tool iterations before the agent halts.")
    actions: List[AgentActionConfig] = Field(default_factory=list)
