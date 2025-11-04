from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.transport.ssh import SshConnectionConfig
from .common import GatewayType, CommonGatewayConfig

class SshTunnelGatewayConfig(CommonGatewayConfig):
    type: Literal[GatewayType.SSH_TUNNEL]
    connection: SshConnectionConfig = Field(..., description="SSH connection configuration.")
    port: List[Tuple[int, int]] = Field(..., min_length=1, description="One or more port forwarding configuration.")

    @model_validator(mode="before")
    def normalize_port(cls, values):
        port = values.get("port")
        if not isinstance(port, list):
            port = [ port ]
        values["port"] = [ cls.normalize_single_port(value) for value in port ]
        return values

    @classmethod
    def normalize_single_port(cls, value) -> Optional[Tuple[int, int]]:
        if isinstance(value, str):
            return tuple(int(port) for port in value.split(":"))
        if isinstance(value, int):
            return ( value, value )
        return None
