from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class ModelMemoryActionMethod(str, Enum):
    APPEND = "append"
    SAVE   = "save"
    LOAD   = "load"
    CLEAR  = "clear"
    DELETE = "delete"

class CommonModelMemoryActionConfig(CommonActionConfig):
    method: ModelMemoryActionMethod = Field(..., description="Memory operation method.")
    session_id: str = Field(default="__session__", description="Session identifier.")

class ModelMemoryAppendActionConfig(CommonModelMemoryActionConfig):
    method: Literal[ModelMemoryActionMethod.APPEND]
    messages: Union[List[Any], str] = Field(..., description="Messages to append.")

class ModelMemorySaveActionConfig(CommonModelMemoryActionConfig):
    method: Literal[ModelMemoryActionMethod.SAVE]
    messages: Optional[Union[List[Any], str]] = Field(default=None, description="Messages to append before saving.")

class ModelMemoryLoadActionConfig(CommonModelMemoryActionConfig):
    method: Literal[ModelMemoryActionMethod.LOAD]

class ModelMemoryClearActionConfig(CommonModelMemoryActionConfig):
    method: Literal[ModelMemoryActionMethod.CLEAR]

class ModelMemoryDeleteActionConfig(CommonModelMemoryActionConfig):
    method: Literal[ModelMemoryActionMethod.DELETE]

ModelMemoryActionConfig = Annotated[
    Union[
        ModelMemoryAppendActionConfig,
        ModelMemorySaveActionConfig,
        ModelMemoryLoadActionConfig,
        ModelMemoryClearActionConfig,
        ModelMemoryDeleteActionConfig,
    ],
    Field(discriminator="method")
]
