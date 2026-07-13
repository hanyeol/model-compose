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
    max_turn_count: Optional[int] = Field(default=None, description="Max recent turns to keep.")
    max_message_count: Optional[int] = Field(default=None, description="Max recent messages to keep (respects turn boundaries).")

    @model_validator(mode="after")
    def validate_limits(self):
        if not self.max_turn_count and not self.max_message_count:
            raise ValueError("window requires at least one of max_turn_count or max_message_count")
        return self

class ModelMemorySummaryConfig(BaseModel):
    component: str = Field(..., description="Component ID to use for summarization.")
    action: str = Field(default="__default__", description="Action ID on the summary component.")
    instruction: Optional[str] = Field(default=None, description="Summary instruction prompt. If omitted, a built-in default is used.")
    input: Optional[Dict[str, Any]] = Field(default=None, description="Input mapping for the summary component.")

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
            values["window"] = { "max_turn_count": window }
        return values
