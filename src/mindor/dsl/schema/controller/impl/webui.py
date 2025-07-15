from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerWebUIDriver(str, Enum):
    GRADIO = "gradio"

class ControllerWebUIConfig(BaseModel):
    driver: ControllerWebUIDriver = Field(default=ControllerWebUIDriver.GRADIO)
    host: Optional[str] = Field(default="0.0.0.0")
    port: Optional[int] = Field(default=8081)
