from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import HttpClientActionConfig, PollingCompletionConfig
from .common import ComponentType, CommonComponentConfig

class HttpClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTTP_CLIENT]
    base_url: Optional[str] = Field(default=None)
    headers: Dict[str, Any] = Field(default_factory=dict)
    actions: Dict[str, HttpClientActionConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(HttpClientActionConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = { "__default__": { k: values.pop(k) for k in action_keys if k in values } }
        return values

    @model_validator(mode="after")
    def validate_baseurl_for_actions(self):
        for action_id, action in self.actions.items():
            if action.path and not self.base_url:
                raise ValueError(f"Action '{action_id}' uses 'path' but 'base_url' is not set in the component.")
        return self

    @model_validator(mode="after")
    def validate_baseurl_for_completion(self):
        for action_id, action in self.actions.items():
            if isinstance(action.completion, PollingCompletionConfig):
                if action.completion.path and not self.base_url:
                    raise ValueError(f"Completion for action '{action_id}' uses 'path' but 'base_url' is not set in the component.")
        return self
