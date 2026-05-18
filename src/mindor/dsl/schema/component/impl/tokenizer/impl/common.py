from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.utils.path import is_local_path
from ...common import CommonComponentConfig, ComponentType
from ...model.impl.common import ModelConfig, ModelProvider

class TokenizerTaskType(str, Enum):
    TEXT = "text"

class TokenizerDriver(str, Enum):
    HUGGINGFACE = "huggingface"

class CommonTokenizerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.TOKENIZER]
    task: TokenizerTaskType = Field(..., description="Type of task the tokenizer performs.")
    driver: TokenizerDriver = Field(default=TokenizerDriver.HUGGINGFACE, description="Tokenizer driver to use.")
    model: Union[str, ModelConfig] = Field(..., description="Model source configuration for the tokenizer.")
    use_fast: Union[bool, str] = Field(default=True, description="Whether to use the fast tokenizer if available.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }
        return values

    @model_validator(mode="before")
    def fill_missing_model_provider(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            model["provider"] = ModelProvider.HUGGINGFACE
        return values
