from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import McpServerActionConfig
from .common import ComponentType, CommonComponentConfig

class McpServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MCP_SERVER]
    actions: Dict[str, McpServerActionConfig] = Field(default_factory=dict)
