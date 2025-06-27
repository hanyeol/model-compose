from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import McpClientActionConfig
from .common import ComponentType, CommonComponentConfig

class McpClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MCP_CLIENT]
    endpoint: Optional[str] = None
    actions: Optional[Dict[str, McpClientActionConfig]] = Field(default_factory=dict)
