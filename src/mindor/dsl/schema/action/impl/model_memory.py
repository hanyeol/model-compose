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
    method: ModelMemoryActionMethod = Field(..., description="Memory operation this action performs.")
    session_id: str = Field(default="__session__", description="Identifier of the conversation session this action targets.")

class ModelMemoryAppendActionConfig(CommonModelMemoryActionConfig):
    method: Literal[ModelMemoryActionMethod.APPEND]
    messages: Union[List[Any], str] = Field(..., description="Messages appended to the session memory.")

class ModelMemorySaveActionConfig(CommonModelMemoryActionConfig):
    method: Literal[ModelMemoryActionMethod.SAVE]
    messages: Optional[Union[List[Any], str]] = Field(default=None, description="Messages appended to the session before it is persisted.")

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
