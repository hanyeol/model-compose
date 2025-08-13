from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class TextEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_EMBEDDING]
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(TextEmbeddingModelActionConfig.model_fields.keys()) - set(CommonModelComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
