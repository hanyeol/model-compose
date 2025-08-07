from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ControllerType, CommonControllerConfig

class McpServerControllerConfig(CommonControllerConfig):
    type: Literal[ControllerType.MCP_SERVER]
    host: str = Field(default="0.0.0.0", description="Host address to bind the MCP server to.")
    port: int = Field(default=8080, description="Port number on which the MCP server will listen.")
    base_path: Optional[str] = Field(default=None, description="Base path to prefix all MCP endpoints")
