from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import HttpClientActionConfig, HttpClientPollingCompletionConfig
from .common import ComponentType, CommonComponentConfig

class HttpClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTTP_CLIENT]
    base_url: Optional[str] = Field(default=None, description="Base URL for HTTP requests.")
    headers: Dict[str, Any] = Field(default_factory=dict, description="Default HTTP headers to include in all requests.")
    actions: List[HttpClientActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(HttpClientActionConfig.model_fields.keys()) - set(CommonComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values

    @model_validator(mode="after")
    def validate_baseurl_for_actions(self):
        for action in self.actions:
            if action.path and not self.base_url:
                raise ValueError(f"Action '{action.id}' uses 'path' but 'base_url' is not set in the component.")
        return self

    @model_validator(mode="after")
    def validate_baseurl_for_completion(self):
        for action in self.actions:
            if isinstance(action.completion, HttpClientPollingCompletionConfig):
                if action.completion.path and not self.base_url:
                    raise ValueError(f"Completion for action '{action.id}' uses 'path' but 'base_url' is not set in the component.")
        return self
