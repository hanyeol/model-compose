from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator

class SshAuthType(str, Enum):
    KEYFILE  = "keyfile"
    PASSWORD = "password"

class CommonSshAuthConfig(BaseModel):
    type: SshAuthType = Field(..., description="Type of SSH authentication.")
    username: str = Field(..., description="Username used for the SSH connection.")

class SshKeyfileAuthConfig(CommonSshAuthConfig):
    type: Literal[SshAuthType.KEYFILE]
    keyfile: str = Field(..., description="Filesystem path to the SSH private key file.")
    passphrase: Optional[str] = Field(default=None, description="Passphrase for decrypting the private key, if encrypted.")

class SshPasswordAuthConfig(CommonSshAuthConfig):
    type: Literal[SshAuthType.PASSWORD]
    password: str = Field(..., description="Password used for SSH authentication.")

SshAuthConfig = Annotated[
    Union[ 
        SshKeyfileAuthConfig,
        SshPasswordAuthConfig,
    ],
    Field(discriminator="type")
]

class SshConnectionConfig(BaseModel):
    host: str = Field(..., description="Hostname or IP address of the SSH server.")
    port: int = Field(default=22, ge=1, le=65535, description="TCP port the SSH server listens on.")
    auth: SshAuthConfig = Field(..., description="Authentication settings used for the SSH connection.")
    keepalive_interval: Union[str, int, float] = Field(default="10s", description="Interval between SSH keepalive messages; '0s' disables keepalive.")
    watch_interval: Union[str, int, float] = Field(default="5s", description="Interval between SSH connection health checks.")
    retry_interval: Union[str, int, float] = Field(default="5s", description="Delay between successive SSH reconnection attempts.")
    max_retry_count: int = Field(default=0, ge=0, description="Maximum number of SSH reconnection attempts; 0 means unlimited.")
