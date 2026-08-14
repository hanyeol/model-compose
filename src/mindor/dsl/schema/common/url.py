from typing import Literal, Union, Optional, Dict, Any
from pydantic import BaseModel, Field

class UrlFetchConfig(BaseModel):
    endpoint: str = Field(..., description="Full URL of the resource to fetch.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="HTTP method used for the fetch request.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers sent with the fetch request.")
    body: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Request body sent with the fetch, as a raw string or a JSON-serializable object.")
    timeout: Optional[float] = Field(default=None, description="Maximum seconds to wait for the fetch response before failing.")
