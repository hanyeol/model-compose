from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .types import GatewayType

class CommonGatewayConfig(BaseModel):
    type: GatewayType
    runtime: Literal[ "docker", "native" ] = "native"
    port: Optional[int] = 8090
