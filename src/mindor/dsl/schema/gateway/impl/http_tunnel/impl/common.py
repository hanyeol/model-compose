from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import GatewayType, CommonGatewayConfig

class HttpTunnelGatewayDriver(str, Enum):
    NGROK      = "ngrok"
    CLOUDFLARE = "cloudflare"

class CommonHttpTunnelGatewayConfig(CommonGatewayConfig):
    type: Literal[GatewayType.HTTP_TUNNEL]
    driver: HttpTunnelGatewayDriver = Field(..., description="HTTP tunneling service provider.")
    port: List[int] = Field(..., min_length=1, description="One or more local ports to tunnel through the gateway to the public.")
    
    @model_validator(mode="before")
    def normalize_port(cls, values):
        port = values.get("port", 8090)  # Default to 8090 if not specified
        if not isinstance(port, list):
            port = [ port ]
        values["port"] = port
        return values
