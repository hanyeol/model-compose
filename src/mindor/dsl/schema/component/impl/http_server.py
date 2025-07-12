from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import HttpServerActionConfig
from .common import ComponentType, CommonComponentConfig

class HttpServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTTP_SERVER]
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    base_path: Optional[str] = Field(default=None)
    actions: Dict[str, HttpServerActionConfig] = Field(default_factory=dict)
