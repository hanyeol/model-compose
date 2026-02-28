from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import WebScraperActionConfig
from .common import ComponentType, CommonComponentConfig

class WebScraperComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEB_SCRAPER]
    headers: Dict[str, str] = Field(default_factory=dict, description="Default HTTP headers to include in all requests")
    cookies: Dict[str, str] = Field(default_factory=dict, description="Default cookies to include in all requests")
    timeout: Optional[str] = Field(default="60s", description="Default timeout for all requests")
    actions: List[WebScraperActionConfig] = Field(default_factory=list)
