from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class WebBrowserDriver(str, Enum):
    CHROME = "chrome"
    PLAYWRIGHT = "playwright"

class CommonWebBrowserComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEB_BROWSER]
    driver: WebBrowserDriver = Field(default=WebBrowserDriver.CHROME, description="Browser driver.")
    timeout: Optional[str] = Field(default="30s", description="Default command timeout for all actions.")
