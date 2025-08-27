from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerWebUIDriver(str, Enum):
    GRADIO  = "gradio"
    STATIC  = "static"
    DYNAMIC = "dynamic"

class CommonWebUIConfig(BaseModel):
    driver: ControllerWebUIDriver = Field(..., description="Web UI rendering mode.")
    host: str = Field(default="0.0.0.0", description="Host address to bind the Web UI server to.")
    port: int = Field(default=8081, description="Port number to serve the Web UI on.")
