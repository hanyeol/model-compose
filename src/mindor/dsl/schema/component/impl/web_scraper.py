from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import WebScraperActionConfig
from .common import ComponentType, CommonComponentConfig

class WebScraperComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEB_SCRAPER]
    headers: Dict[str, str] = Field(default_factory=dict, description="Default HTTP headers to include in all requests")
    cookies: Dict[str, str] = Field(default_factory=dict, description="Default cookies to include in all requests")
    timeout: Optional[str] = Field(default="60s", description="Default timeout for all requests")
    actions: List[WebScraperActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(WebScraperActionConfig.model_fields.keys()) - set(CommonComponentConfig.model_fields.keys())
            action_keys = action_keys - { "headers", "cookies", "timeout" }
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
