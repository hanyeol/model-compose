from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ControllerType, CommonControllerConfig

class HttpServerControllerConfig(CommonControllerConfig):
    type: Literal[ControllerType.HTTP_SERVER]
    host: str = Field(default="0.0.0.0", description="Host address to bind the HTTP server to.")
    port: int = Field(default=8080, description="Port number on which the HTTP server will listen.")
    base_path: Optional[str] = Field(default=None, description="Base path to prefix all API routes")
    origins: Optional[str] = Field(default="*", description="CORS allowed origins, specified as a comma-separated string")
