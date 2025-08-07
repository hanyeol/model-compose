from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class McpServerActionConfig(CommonActionConfig):
    tool: str = Field(default="__default__", description="Name of the tool to invoke.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool.")
    headers: Dict[str, str] = Field(default_factory=dict, description="Optional HTTP headers to include in the tool call.")
