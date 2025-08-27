from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.runtime import RuntimeType
from .types import GatewayType

class CommonGatewayConfig(BaseModel):
    type: GatewayType = Field(..., description="Type of gateway service.")
    runtime: RuntimeType = Field(default=RuntimeType.NATIVE, description="Runtime environment for executing the gateway service.")
    port: int = Field(default=8090, description="Local port to tunnel through the gateway to the public.")
