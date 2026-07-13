from typing import Union, Literal, Optional, Dict, List
from pydantic import BaseModel, Field

class AppleContainerBuildConfig(BaseModel):
    context: Optional[str] = Field(default=None, description="Build context path.")
    dockerfile: Optional[str] = Field(default=None, description="Path to Dockerfile relative to context.")
    args: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Build arguments as key-value pairs.")
    target: Optional[str] = Field(default=None, description="Target build stage in multi-stage builds.")
    labels: Optional[Dict[str, str]] = Field(default=None, description="Image labels to apply at build time.")
    pull: Optional[bool] = Field(default=None, description="Always pull newer versions of base images.")

class AppleContainerPortConfig(BaseModel):
    container_port: int = Field(..., description="Port exposed by the container.")
    host_port: Optional[int] = Field(default=None, description="Host port to publish.")
    host_ip: Optional[str] = Field(default=None, description="Host IP to bind published port to (e.g. 127.0.0.1). Defaults to all interfaces.")
    protocol: Optional[Literal["tcp", "udp"]] = Field(default="tcp", description="Protocol.")

class AppleContainerVolumeConfig(BaseModel):
    type: Optional[Literal["bind", "volume"]] = Field(default=None, description="Mount type.")
    target: str = Field(..., description="Mount path inside the container.")
    source: Optional[str] = Field(default=None, description="Host path (bind) or volume name (volume).")
    name: Optional[str] = Field(default=None, description="Volume name (alias for `source` when type=volume).")
    read_only: Optional[bool] = Field(default=None, description="Mount as read-only.")

class AppleContainerHealthCheck(BaseModel):
    test: Union[str, List[str]] = Field(..., description="Health check command.")
    interval: Union[str, int, float] = Field(default="30s", description="Time between checks.")
    timeout: Union[str, int, float] = Field(default="30s", description="Timeout for each check.")
    max_retry_count: Optional[int] = Field(default=3, description="Failures before marking as unhealthy.")
    start_period: Optional[Union[str, int, float]] = Field(default="0s", description="Startup grace period before checks begin.")

class AppleContainerConfig(BaseModel):
    # Image or build
    image: Optional[str] = Field(default=None, description="Container image name with optional tag.")
    build: Optional[AppleContainerBuildConfig] = Field(default=None, description="Build config for building the image locally.")
    # Container identity
    container_name: Optional[str] = Field(default=None, description="Name of the container.")
    # Networking
    ports: Optional[List[Union[str, int, AppleContainerPortConfig]]] = Field(default=None, description="Port mappings (e.g., '8080:80', 8080).")
    networks: Optional[List[str]] = Field(default=None, description="Networks to attach the container to.")
    # Volumes
    volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]] = Field(default=None, description="Volume mounts.")
    # Environment variables
    environment: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Environment variables.")
    env_file: Optional[Union[str, List[str]]] = Field(default=None, description="Environment files.")
    # Command overrides
    command: Optional[Union[str, List[str]]] = Field(default=None, description="Override the default command.")
    entrypoint: Optional[Union[str, List[str]]] = Field(default=None, description="Override the entrypoint.")
    working_dir: Optional[str] = Field(default=None, description="Working directory inside the container.")
    user: Optional[str] = Field(default=None, description="User to run the container as.")
    # Resource limits
    cpus: Optional[Union[str, float]] = Field(default=None, description="CPU core limit.")
    mem_limit: Optional[str] = Field(default=None, description="Memory limit (e.g., '1G', '512M').")
    # Health check
    healthcheck: Optional[AppleContainerHealthCheck] = Field(default=None, description="Health check configuration.")
    # Miscellaneous
    labels: Optional[Dict[str, str]] = Field(default=None, description="Container labels.")
