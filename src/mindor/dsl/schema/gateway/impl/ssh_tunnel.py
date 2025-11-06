from typing import Type, Union, Literal, Optional, Dict, List, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.transport.ssh import SshConnectionConfig, SshAuthConfig
from .common import GatewayType, CommonGatewayConfig

class SshTunnelGatewayConfig(CommonGatewayConfig):
    type: Literal[GatewayType.SSH_TUNNEL]
    connection: SshConnectionConfig = Field(..., description="SSH connection configuration.")
    port: List[List[int | str]] = Field(..., min_length=1, description="One or more port forwarding configuration.")

    @model_validator(mode="before")
    def normalize_port(cls, values):
        port = values.get("port", 8090)  # Default to 8090 if not specified
        if not isinstance(port, list):
            port = [ port ]
        values["port"] = [ cls.normalize_single_port(value) for value in port ]
        return values

    @classmethod
    def normalize_single_port(cls, value) -> Optional[List[int | str]]:
        if isinstance(value, str):
            parts = value.split(":")

            if len(parts) == 2 and parts[0].isdigit():
                if parts[1].isdigit():  # "8080:3000" (port:port)
                    return [int(parts[0]), "localhost", int(parts[1])]
                else:  # "8080:192.168.1.107" or "8080:example.com" (port:host)
                    return [int(parts[0]), parts[1], int(parts[0])]

            if len(parts) == 3:  # "8080:192.168.1.107:3000" (port:host:port)
                return [int(parts[0]), parts[1], int(parts[2])]

            return None

        if isinstance(value, int):
            return [value, "localhost", value]

        if isinstance(value, list):
            return value

        return None
