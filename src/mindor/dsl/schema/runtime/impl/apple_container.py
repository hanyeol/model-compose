from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import RuntimeType, CommonRuntimeConfig

class AppleContainerBuildConfig(BaseModel):
    context: Optional[str] = Field(default=None, description="Build context path.")
    dockerfile: Optional[str] = Field(default=None, description="Path to Dockerfile relative to context.")
    args: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Build arguments as key-value pairs.")

class AppleContainerVolumeConfig(BaseModel):
    name: str = Field(..., description="Volume name.")
    target: str = Field(..., description="Mount path inside the container.")
    read_only: Optional[bool] = Field(default=None, description="Mount as read-only.")

class AppleContainerDnsConfig(BaseModel):
    domain: str = Field(..., description="DNS domain name (e.g., 'test', 'dev').")
    hostname: Optional[str] = Field(default=None, description="Container hostname within the domain.")

class AppleContainerHealthCheck(BaseModel):
    test: Union[str, List[str]] = Field(..., description="Health check command.")
    interval: str = Field(default="30s", description="Time between checks.")
    timeout: str = Field(default="30s", description="Timeout for each check.")
    max_retry_count: Optional[int] = Field(default=3, description="Number of failures before marking as unhealthy.")
    start_period: Optional[str] = Field(default="0s", description="Startup grace period before checks start.")

class AppleContainerRuntimeConfig(CommonRuntimeConfig):
    type: Literal[RuntimeType.APPLE_CONTAINER]
    # Image or build
    image: Optional[str] = Field(default=None, description="Container image name with optional tag.")
    build: Optional[AppleContainerBuildConfig] = Field(default=None, description="Build configuration for building image locally.")
    # Container identity
    container_name: Optional[str] = Field(default=None, description="Name of the container.")
    # Networking
    ports: Optional[List[Union[str, int]]] = Field(default=None, description="Port mappings (e.g., '8080:80', 8080).")
    dns: Optional[AppleContainerDnsConfig] = Field(default=None, description="DNS domain configuration for dedicated IP access.")
    # Volumes
    volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]] = Field(default=None, description="Named volume mounts.")
    # Environment variables
    environment: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Environment variables.")
    # Command overrides
    command: Optional[Union[str, List[str]]] = Field(default=None, description="Override the default command.")
    # Resource limits
    cpus: Optional[Union[str, float]] = Field(default=None, description="CPU core limit.")
    mem_limit: Optional[str] = Field(default=None, description="Memory limit (e.g., '1G', '512M').")
    # Health check
    healthcheck: Optional[AppleContainerHealthCheck] = Field(default=None, description="Health check configuration.")
    # Miscellaneous
    labels: Optional[Dict[str, str]] = Field(default=None, description="Container labels.")
