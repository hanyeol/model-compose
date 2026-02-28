from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import McpClientActionConfig
from .common import ComponentType, CommonComponentConfig

class McpClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MCP_CLIENT]
    url: str = Field(..., description="URL of the MCP server to invoke tools.")
    headers: Dict[str, Any] = Field(default_factory=dict, description="HTTP headers to include when connecting to the MCP server.")
    actions: List[McpClientActionConfig] = Field(default_factory=list)
