from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import WebScraperActionConfig
from .common import ComponentType, CommonComponentConfig
from mindor.dsl.schema.common.rate_limit import RateLimitConfig, inflate_rate_limit_shorthand

class WebScraperComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEB_SCRAPER]
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with every scraper request.")
    cookies: Dict[str, str] = Field(default_factory=dict, description="Cookies sent with every scraper request.")
    timeout: Optional[Union[str, int, float]] = Field(default="60s", description="Maximum seconds to wait for a scraper request before failing.")
    rate_limit: Optional[RateLimitConfig] = Field(default=None, description="Rate limit applied across all actions in this scraper.")
    actions: List[WebScraperActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_rate_limit(cls, values: Dict[str, Any]):
        rate_limit = values.get("rate_limit")
        if isinstance(rate_limit, str):
            values["rate_limit"] = inflate_rate_limit_shorthand(rate_limit)
        return values
