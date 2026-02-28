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

    @model_validator(mode="after")
    def validate_baseurl_for_actions(self):
        for action in self.actions:
            if action.path and not self.base_url:
                raise ValueError(f"Action '{action.id}' uses 'path' but 'base_url' is not set in the component")
        return self

    @model_validator(mode="after")
    def validate_baseurl_for_completion(self):
        for action in self.actions:
            if isinstance(action.completion, HttpClientPollingCompletionConfig):
                if action.completion.path and not self.base_url:
                    raise ValueError(f"Completion for action '{action.id}' uses 'path' but 'base_url' is not set in the component")
        return self
