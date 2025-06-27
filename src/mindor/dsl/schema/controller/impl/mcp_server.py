from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ControllerType, CommonControllerConfig

class McpServerControllerConfig(CommonControllerConfig):
    type: Literal[ControllerType.MCP_SERVER]
    port: Optional[int] = 8080
