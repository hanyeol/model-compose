from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .types import ControllerAdapterType
from ..common import CommonControllerAdapterConfig

class McpServerTransport(str, Enum):
    HTTP  = "http"
    STDIO = "stdio"

class McpServerControllerAdapterConfig(CommonControllerAdapterConfig):
    type: Literal[ControllerAdapterType.MCP_SERVER]
    transport: McpServerTransport = Field(default=McpServerTransport.HTTP, description="Transport used by the MCP server (e.g., http, stdio).")
    disable_dns_rebinding_protection: bool = Field(default=False, description="Whether to skip the DNS-rebinding Host/Origin header check.")
    allowed_hosts: Optional[List[str]] = Field(default=None, description="Allowed Host header values, as glob patterns (e.g., `example.com`, `*.example.com`).")
    allowed_origins: Optional[List[str]] = Field(default=None, description="Allowed Origin header values, as glob patterns (e.g., `https://example.com`).")

    @model_validator(mode="after")
    def validate_transport_security(self):
        if self.disable_dns_rebinding_protection and (self.allowed_hosts is not None or self.allowed_origins is not None):
            raise ValueError(
                "'disable_dns_rebinding_protection' cannot be combined with 'allowed_hosts' or 'allowed_origins'."
            )
        return self
