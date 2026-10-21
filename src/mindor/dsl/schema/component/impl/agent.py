from typing import Union, Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.action import AgentActionConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from ..common import ComponentRunConfig
from .common import ComponentType, CommonComponentConfig

class AgentComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AGENT]
    model: ComponentRunConfig = Field(..., description="LLM backend the agent uses for reasoning and tool calls.")
    instructions: Optional[str] = Field(default=None, description="System-message text that sets the agent's persona and behavior.")
    tools: List[Union[str, ModelTool]] = Field(default_factory=list, description="Workflow IDs or tool schemas the agent may call.")
    max_iteration_count: int = Field(default=32, description="Maximum number of reasoning-and-tool iterations before the agent halts.")
    actions: List[AgentActionConfig] = Field(default_factory=list)
