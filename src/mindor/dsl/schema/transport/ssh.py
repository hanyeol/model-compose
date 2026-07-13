from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator

class SshAuthType(str, Enum):
    KEYFILE  = "keyfile"
    PASSWORD = "password"

class CommonSshAuthConfig(BaseModel):
    type: SshAuthType = Field(..., description="SSH authentication type.")
    username: str = Field(..., description="SSH connection username.")

class SshKeyfileAuthConfig(CommonSshAuthConfig):
    type: Literal[SshAuthType.KEYFILE]
    keyfile: str = Field(..., description="Path to the SSH private key file.")

class SshPasswordAuthConfig(CommonSshAuthConfig):
    type: Literal[SshAuthType.PASSWORD]
    password: str = Field(..., description="Password for SSH authentication.")

SshAuthConfig = Annotated[
    Union[ 
        SshKeyfileAuthConfig,
        SshPasswordAuthConfig,
    ],
    Field(discriminator="type")
]

class SshConnectionConfig(BaseModel):
    host: str = Field(..., description="SSH server host address.")
    port: int = Field(default=22, ge=1, le=65535, description="SSH server port.")
    auth: SshAuthConfig = Field(..., description="SSH authentication config.")
    keepalive_interval: Union[str, int, float] = Field(default="10s", description="SSH keepalive interval. '0s' to disable.")
    watch_interval: Union[str, int, float] = Field(default="5s", description="Interval between SSH health checks.")
    retry_interval: Union[str, int, float] = Field(default="5s", description="Interval between reconnection attempts.")
    max_retry_count: int = Field(default=0, ge=0, description="Max reconnection attempts. 0 for unlimited.")
