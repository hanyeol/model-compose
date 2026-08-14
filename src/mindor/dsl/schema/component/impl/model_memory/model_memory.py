from typing import Union, Literal, Optional, Dict, List, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import ModelMemoryActionConfig
from .impl import *
from ..common import CommonComponentConfig, ComponentType

ModelMemoryStorageConfig = Annotated[
    Union[
        SqliteModelMemoryStorageConfig,
        RedisModelMemoryStorageConfig
    ],
    Field(discriminator="driver")
]

ModelMemoryBufferConfig = Annotated[
    Union[
        MemoryModelMemoryBufferConfig,
        RedisModelMemoryBufferConfig,
    ],
    Field(discriminator="driver")
]

class ModelMemoryWindowConfig(BaseModel):
    max_turn_count: Optional[int] = Field(default=None, description="Maximum number of recent conversation turns retained in the window.")
    max_message_count: Optional[int] = Field(default=None, description="Maximum number of recent messages retained in the window, respecting turn boundaries.")

    @model_validator(mode="after")
    def validate_limits(self):
        if not self.max_turn_count and not self.max_message_count:
            raise ValueError("window requires at least one of max_turn_count or max_message_count")
        return self

class ModelMemorySummaryConfig(BaseModel):
    component: str = Field(..., description="ID of the component that generates conversation summaries.")
    action: str = Field(default="__default__", description="Action on the summary component invoked to produce a summary.")
    instruction: Optional[str] = Field(default=None, description="Prompt guiding the summarizer; a built-in default is used when omitted.")
    input: Optional[Dict[str, Any]] = Field(default=None, description="Input mapping passed to the summary component.")

class ModelMemoryComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_MEMORY]
    buffer: ModelMemoryBufferConfig = Field(default_factory=MemoryModelMemoryBufferConfig, description="Short-term buffer holding recent conversation turns.")
    storage: ModelMemoryStorageConfig = Field(default_factory=SqliteModelMemoryStorageConfig, description="Long-term persistent storage for conversation history.")
    window: Optional[Union[int, ModelMemoryWindowConfig]] = Field(default=None, description="Sliding window over recent history; an integer is shorthand for max_turn_count.")
    summary: Optional[ModelMemorySummaryConfig] = Field(default=None, description="Summarization settings used to compress older history.")
    actions: List[ModelMemoryActionConfig] = Field(default_factory=list, description="Actions this memory component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_window(cls, values: Dict[str, Any]):
        window = values.get("window")
        if isinstance(window, int):
            values["window"] = { "max_turn_count": window }
        return values
