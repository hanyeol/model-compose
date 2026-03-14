from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import HttpTunnelGatewayDriver, CommonHttpTunnelGatewayConfig

class CloudflareHttpTunnelGatewayConfig(CommonHttpTunnelGatewayConfig):
    driver: Literal[HttpTunnelGatewayDriver.CLOUDFLARE]
    token: Optional[str] = Field(default=None, description="Cloudflare Tunnel token for remotely-managed named tunnels.")
    tunnel: Optional[str] = Field(default=None, description="Tunnel UUID or name for locally-managed named tunnels.")
    credentials_file: Optional[str] = Field(default=None, description="Path to credentials JSON file for locally-managed named tunnels.")
    hostname: Optional[str] = Field(default=None, description="Public hostname for the tunnel (e.g. app.example.com).")

    @model_validator(mode="after")
    def validate_named_tunnel_config(self):
        if self.tunnel and not self.credentials_file:
            raise ValueError("'credentials_file' is required when 'tunnel' is specified.")
        if self.credentials_file and not self.tunnel:
            raise ValueError("'tunnel' is required when 'credentials_file' is specified.")
        if self.token and self.tunnel:
            raise ValueError("Cannot specify both 'token' and 'tunnel'/'credentials_file'.")
        return self
