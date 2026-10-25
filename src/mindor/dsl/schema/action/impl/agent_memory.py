from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class AgentMemoryActionMethod(str, Enum):
    APPEND = "append"
    SAVE   = "save"
    LOAD   = "load"
    CLEAR  = "clear"
    DELETE = "delete"

class CommonAgentMemoryActionConfig(CommonActionConfig):
    method: AgentMemoryActionMethod = Field(..., description="Memory operation this action performs.")
    session_id: str = Field(default="__session__", description="Identifier of the conversation session this action targets.")

class AgentMemoryAppendActionConfig(CommonAgentMemoryActionConfig):
    method: Literal[AgentMemoryActionMethod.APPEND]
    messages: Union[List[Any], str] = Field(..., description="Messages appended to the session memory.")

class AgentMemorySaveActionConfig(CommonAgentMemoryActionConfig):
    method: Literal[AgentMemoryActionMethod.SAVE]
    messages: Optional[Union[List[Any], str]] = Field(default=None, description="Messages appended to the session before it is persisted.")

class AgentMemoryLoadActionConfig(CommonAgentMemoryActionConfig):
    method: Literal[AgentMemoryActionMethod.LOAD]

class AgentMemoryClearActionConfig(CommonAgentMemoryActionConfig):
    method: Literal[AgentMemoryActionMethod.CLEAR]

class AgentMemoryDeleteActionConfig(CommonAgentMemoryActionConfig):
    method: Literal[AgentMemoryActionMethod.DELETE]

AgentMemoryActionConfig = Annotated[
    Union[
        AgentMemoryAppendActionConfig,
        AgentMemorySaveActionConfig,
        AgentMemoryLoadActionConfig,
        AgentMemoryClearActionConfig,
        AgentMemoryDeleteActionConfig,
    ],
    Field(discriminator="method")
]
