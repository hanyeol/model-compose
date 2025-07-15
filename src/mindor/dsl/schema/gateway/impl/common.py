from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.runtime import RuntimeType
from .types import GatewayType

class CommonGatewayConfig(BaseModel):
    type: GatewayType = Field(..., description="")
    runtime: RuntimeType = Field(default=RuntimeType.NATIVE)
    port: Optional[int] = Field(default=8090)
