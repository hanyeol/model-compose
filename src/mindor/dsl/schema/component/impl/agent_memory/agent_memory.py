from typing import Union, Literal, Optional, Dict, List, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import AgentMemoryActionConfig
from .impl import *
from ...common import ComponentRunConfig
from ..common import CommonComponentConfig, ComponentType

AgentMemoryStorageConfig = Annotated[
    Union[
        SqliteAgentMemoryStorageConfig,
        RedisAgentMemoryStorageConfig
    ],
    Field(discriminator="driver")
]

AgentMemoryBufferConfig = Annotated[
    Union[
        MemoryAgentMemoryBufferConfig,
        RedisAgentMemoryBufferConfig,
    ],
    Field(discriminator="driver")
]

class AgentMemoryWindowConfig(BaseModel):
    max_turn_count: Optional[int] = Field(default=None, description="Maximum number of recent conversation turns retained in the window.")
    max_message_count: Optional[int] = Field(default=None, description="Maximum number of recent messages retained in the window, respecting turn boundaries.")

    @model_validator(mode="after")
    def validate_limits(self):
        if not self.max_turn_count and not self.max_message_count:
            raise ValueError("window requires at least one of max_turn_count or max_message_count")
        return self

class AgentMemorySummaryConfig(ComponentRunConfig):
    instruction: Optional[str] = Field(default=None, description="Prompt guiding the summarizer; a built-in default is used when omitted.")

class AgentMemoryComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AGENT_MEMORY]
    buffer: AgentMemoryBufferConfig = Field(default_factory=MemoryAgentMemoryBufferConfig, description="Short-term buffer holding recent conversation turns.")
    storage: AgentMemoryStorageConfig = Field(default_factory=SqliteAgentMemoryStorageConfig, description="Long-term persistent storage for conversation history.")
    window: Optional[Union[int, AgentMemoryWindowConfig]] = Field(default=None, description="Sliding window over recent history; an integer is shorthand for max_turn_count.")
    summary: Optional[AgentMemorySummaryConfig] = Field(default=None, description="Summarization settings used to compress older history.")
    actions: List[AgentMemoryActionConfig] = Field(default_factory=list, description="Actions this memory component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_window(cls, values: Dict[str, Any]):
        window = values.get("window")
        if isinstance(window, int):
            values["window"] = { "max_turn_count": window }
        return values
