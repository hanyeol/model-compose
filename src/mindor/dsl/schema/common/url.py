from typing import Literal, Union, Optional, Dict, Any
from pydantic import BaseModel, Field

class UrlFetchConfig(BaseModel):
    endpoint: str = Field(..., description="URL to fetch.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="HTTP method.")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers to send with the request.")
    body: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Request body (raw string or JSON-serializable object).")
    timeout: Optional[float] = Field(default=None, description="Request timeout in seconds.")
