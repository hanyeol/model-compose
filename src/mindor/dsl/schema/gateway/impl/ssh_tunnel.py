from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.transport.ssh.auth import SshAuthConfig
from .common import GatewayType, CommonGatewayConfig

class SshTunnelGatewayConfig(CommonGatewayConfig):
    type: Literal[GatewayType.SSH_TUNNEL]
    host: str = Field(..., description="Host address of the SSH server to connect to.")
    port: int = Field(default=22, description="Port number used to connect to the SSH server.")
    auth: SshAuthConfig = Field(..., description="SSH authentication configuration.")
