from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .types import ControllerAdapterType
from ..common import CommonControllerAdapterConfig

class McpServerTransport(str, Enum):
    HTTP  = "http"
    STDIO = "stdio"

class McpServerControllerAdapterConfig(CommonControllerAdapterConfig):
    type: Literal[ControllerAdapterType.MCP_SERVER]
    transport: McpServerTransport = Field(default=McpServerTransport.HTTP, description="MCP transport mode (http streamable or stdio).")
