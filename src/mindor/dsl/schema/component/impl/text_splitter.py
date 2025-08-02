from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TextSplitterActionConfig
from .common import ComponentType, CommonComponentConfig

class TextSplitterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.TEXT_SPLITTER]
    actions: Optional[Dict[str, TextSplitterActionConfig]] = Field(default_factory=dict, description="Text split actions mapped by an identifier.")

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(TextSplitterActionConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = { "__default__": { k: values.pop(k) for k in action_keys if k in values } }
        return values
