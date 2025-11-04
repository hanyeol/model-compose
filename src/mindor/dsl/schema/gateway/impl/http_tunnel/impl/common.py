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
    port: int = Field(default=8090, ge=1, le=65535, description="Local port to tunnel through the gateway to the public.")
