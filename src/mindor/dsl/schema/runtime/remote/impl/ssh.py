from typing import Literal, Optional
from pydantic import Field
from .common import CommonRemoteTransportConfig
from .types import RemoteTransportType

class SshRemoteTransportConfig(CommonRemoteTransportConfig):
    """Reach the remote host over a plain SSH connection."""
    type: Literal[RemoteTransportType.SSH]
    host: str = Field(..., description="Remote host name or IP address.")
    user: Optional[str] = Field(default=None, description="Login user on the remote host.")
    port: int = Field(default=22, description="SSH port on the remote host.")
    key: Optional[str] = Field(default=None, description="Path to the private key used for authentication; falls back to the SSH agent when unset.")
    key_passphrase: Optional[str] = Field(default=None, description="Passphrase for the private key, when the key is encrypted.")
    password: Optional[str] = Field(default=None, description="Password used for authentication; prefer key-based auth when possible.")
    strict_host_key: bool = Field(default=True, description="Verify the remote host key against known_hosts; disable only in trusted networks.")
    known_hosts: Optional[str] = Field(default=None, description="Path to a known_hosts file; defaults to ~/.ssh/known_hosts.")
    connect_timeout: float = Field(default=10.0, description="Seconds to wait for the SSH handshake before failing.")
    keepalive_interval: float = Field(default=30.0, description="Seconds between SSH keepalive packets; 0 disables.")
