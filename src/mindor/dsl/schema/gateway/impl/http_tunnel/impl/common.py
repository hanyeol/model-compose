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
