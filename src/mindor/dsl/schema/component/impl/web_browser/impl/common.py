from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class WebBrowserDriverType(str, Enum):
    CHROME     = "chrome"
    PLAYWRIGHT = "playwright"

class CommonWebBrowserComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEB_BROWSER]
    driver: WebBrowserDriverType = Field(default=WebBrowserDriverType.CHROME, description="Backend implementation used to drive the browser.")
    timeout: Optional[Union[str, int, float]] = Field(default="30s", description="Maximum seconds to wait for a browser action before failing.")
