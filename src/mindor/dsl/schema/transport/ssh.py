from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator

class SshAuthType(str, Enum):
    KEYFILE  = "keyfile"
    PASSWORD = "password"

class CommonSshAuthConfig(BaseModel):
    type: SshAuthType = Field(..., description="Type of SSH authentication to use.")
    username: str = Field(..., description="Username for the SSH connection.")

class SshKeyfileAuthConfig(CommonSshAuthConfig):
    type: Literal[SshAuthType.KEYFILE]
    keyfile: str = Field(..., description="Path to the private key file for SSH authentication.")

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
    host: str = Field(..., description="Host address of the SSH server to connect to.")
    port: int = Field(default=22, description="Port number used to connect to the SSH server.")
    auth: SshAuthConfig = Field(..., description="SSH authentication configuration.")
