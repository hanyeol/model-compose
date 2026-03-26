from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .types import ControllerAdapterType
from ..common import CommonControllerAdapterConfig

class McpServerControllerAdapterConfig(CommonControllerAdapterConfig):
    type: Literal[ControllerAdapterType.MCP_SERVER]
