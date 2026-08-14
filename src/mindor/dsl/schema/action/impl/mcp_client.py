from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class McpClientActionConfig(CommonActionConfig):
    tool: str = Field(default="__workflow__", description="Name of the MCP tool to invoke.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the MCP tool.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with the MCP tool call.")
