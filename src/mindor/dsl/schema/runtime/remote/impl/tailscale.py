from typing import Literal, Optional
from pydantic import Field
from .common import CommonRemoteTransportConfig
from .types import RemoteTransportType

class TailscaleRemoteTransportConfig(CommonRemoteTransportConfig):
    """Reach the remote host over Tailscale SSH.

    The connection runs over SSH, but authentication is delegated to the
    tailnet ACLs instead of host keys / passwords. When ``tsnet`` is false
    (default), the local ``tailscaled`` daemon is used; when true, an
    embedded tsnet node joins the tailnet with the supplied auth key.
    """
    type: Literal[RemoteTransportType.TAILSCALE]
    host: str = Field(..., description="Target host name on the tailnet (MagicDNS short name, FQDN, or Tailscale IP).")
    user: Optional[str] = Field(default=None, description="Login user on the remote host.")
    port: int = Field(default=22, description="SSH port on the remote host.")
    tsnet: bool = Field(default=False, description="Join the tailnet with an embedded tsnet node instead of using the local tailscaled.")
    auth_key: Optional[str] = Field(default=None, description="Tailscale auth key used by the tsnet node; required when `tsnet` is true.")
    hostname: Optional[str] = Field(default=None, description="Hostname advertised by the tsnet node on the tailnet.")
    state_dir: Optional[str] = Field(default=None, description="Directory where the tsnet node persists its state; defaults to a per-project path.")
    connect_timeout: float = Field(default=10.0, description="Seconds to wait for the SSH handshake before failing.")
    keepalive_interval: float = Field(default=30.0, description="Seconds between SSH keepalive packets; 0 disables.")
