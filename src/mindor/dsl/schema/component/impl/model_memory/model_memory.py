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
    max_turn_count: Optional[int] = Field(default=None, description="Maximum number of recent turns to keep.")
    max_message_count: Optional[int] = Field(default=None, description="Maximum number of recent messages to keep (respects turn boundaries).")

class ModelMemorySummaryConfig(BaseModel):
    component: str = Field(..., description="Component ID to use for summarization.")
    action: str = Field(default="__default__", description="Action ID on the summary component.")
    input: Dict[str, Any] = Field(default_factory=lambda: {"messages": "${messages}"}, description="Input mapping for summary component.")
    instruction: str = Field(default="Summarize the following conversation concisely:", description="Summary instruction prompt.")

class ModelMemoryComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_MEMORY]
    buffer: ModelMemoryBufferConfig = Field(default_factory=MemoryModelMemoryBufferConfig, description="Buffer settings.")
    storage: ModelMemoryStorageConfig = Field(default_factory=SqliteModelMemoryStorageConfig, description="Persistent storage settings.")
    window: Optional[Union[int, ModelMemoryWindowConfig]] = Field(default=None, description="Window settings. Int inflates to max_turn_count.")
    summary: Optional[ModelMemorySummaryConfig] = Field(default=None, description="Summary settings for conversation pruning.")
    actions: List[ModelMemoryActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_window(cls, values: Dict[str, Any]):
        window = values.get("window")
        if isinstance(window, int):
            values["window"] = {"max_turn_count": window}
        return values
