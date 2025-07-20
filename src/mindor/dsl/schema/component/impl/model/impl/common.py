from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType
from .types import ModelTaskType

class CommonModelComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL]
    task: ModelTaskType = Field(..., description="")
    cache_dir: str = Field(default="~/.cache/model-compose", description="")
