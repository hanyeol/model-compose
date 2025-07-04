from enum import Enum

class GatewayType(str, Enum):
    HTTP_TUNNEL = "http-tunnel"
    SSH_TUNNEL  = "ssh-tunnel"
