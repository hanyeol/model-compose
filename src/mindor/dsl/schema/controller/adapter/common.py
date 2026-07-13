from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl.types import ControllerAdapterType

class CommonControllerAdapterConfig(BaseModel):
    type: ControllerAdapterType = Field(..., description="Controller adapter type.")
    host: str = Field(default="127.0.0.1", description="Host address to bind to.")
    port: int = Field(default=8080, ge=1, le=65535, description="Port to listen on.")
    base_path: Optional[str] = Field(default=None, description="Base path prefix for all routes.")
