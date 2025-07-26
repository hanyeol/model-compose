from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ControllerType, CommonControllerConfig

class HttpServerControllerConfig(CommonControllerConfig):
    type: Literal[ControllerType.HTTP_SERVER]
    host: Optional[str] = Field(default="0.0.0.0", description="")
    port: Optional[int] = Field(default=8080, description="")
    base_path: Optional[str] = Field(default=None, description="")
    origins: Optional[str] = Field(default="*", description="")
