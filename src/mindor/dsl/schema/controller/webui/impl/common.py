from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerWebUIDriver(str, Enum):
    GRADIO    = "gradio"
    STATIC    = "static"
    DYNAMIC   = "dynamic"

class CommonWebUIConfig(BaseModel):
    driver: ControllerWebUIDriver = Field(..., description="Backend implementation used to render the Web UI.")
    host: str = Field(default="127.0.0.1", description="Hostname or IP address the Web UI server binds to.")
    port: int = Field(default=8081, ge=1, le=65535, description="TCP port the Web UI server listens on.")
