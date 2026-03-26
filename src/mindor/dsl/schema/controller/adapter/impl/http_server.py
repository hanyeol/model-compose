from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .types import ControllerAdapterType
from ..common import CommonControllerAdapterConfig

class HttpServerControllerAdapterConfig(CommonControllerAdapterConfig):
    type: Literal[ControllerAdapterType.HTTP_SERVER]
    origins: Optional[str] = Field(default="*", description="CORS allowed origins, specified as a comma-separated string")
