from typing import Union, Literal, Optional, Dict, List
from pydantic import BaseModel, Field

class AppleContainerBuildConfig(BaseModel):
    context: Optional[str] = Field(default=None, description="Filesystem path used as the build context.")
    dockerfile: Optional[str] = Field(default=None, description="Path to the Dockerfile, relative to the build context.")
    args: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Build-time arguments passed to the Dockerfile.")
    target: Optional[str] = Field(default=None, description="Target stage to build in a multi-stage Dockerfile.")
    labels: Optional[Dict[str, str]] = Field(default=None, description="Labels applied to the built image.")
    pull: Optional[bool] = Field(default=None, description="Whether to always pull newer versions of base images before building.")

class AppleContainerPortConfig(BaseModel):
    container_port: int = Field(..., description="TCP/UDP port exposed inside the container.")
    host_port: Optional[int] = Field(default=None, description="Port on the host that maps to the container port.")
    host_ip: Optional[str] = Field(default=None, description="Host IP address the published port binds to (e.g., 127.0.0.1); binds to all interfaces when unset.")
    protocol: Optional[Literal["tcp", "udp"]] = Field(default="tcp", description="Transport protocol used for the port mapping.")

class AppleContainerVolumeConfig(BaseModel):
    type: Optional[Literal["bind", "volume"]] = Field(default=None, description="Type of mount (e.g., bind, volume).")
    target: str = Field(..., description="Mount path inside the container.")
    source: Optional[str] = Field(default=None, description="Host path (for bind mounts) or volume name (for volume mounts).")
    name: Optional[str] = Field(default=None, description="Volume name; alias for `source` when `type` is `volume`.")
    read_only: Optional[bool] = Field(default=None, description="Whether the mount is read-only.")

class AppleContainerHealthCheck(BaseModel):
    test: Union[str, List[str]] = Field(..., description="Command executed inside the container to determine health.")
    interval: Union[str, int, float] = Field(default="30s", description="Time between health check invocations.")
    timeout: Union[str, int, float] = Field(default="30s", description="Maximum time a single health check may run before being considered failed.")
    max_retry_count: Optional[int] = Field(default=3, description="Consecutive failures required before the container is marked unhealthy.")
    start_period: Optional[Union[str, int, float]] = Field(default="0s", description="Grace period after startup before health checks begin counting failures.")

class AppleContainerConfig(BaseModel):
    # Image or build
    image: Optional[str] = Field(default=None, description="Container image reference with optional tag. Mutually exclusive with `build`.")
    build: Optional[AppleContainerBuildConfig] = Field(default=None, description="Settings for building the image locally instead of pulling.")
    # Container identity
    container_name: Optional[str] = Field(default=None, description="Name assigned to the container.")
    # Networking
    ports: Optional[List[Union[str, int, AppleContainerPortConfig]]] = Field(default=None, description="Port mappings between the host and the container (e.g., '8080:80', 8080).")
    networks: Optional[List[str]] = Field(default=None, description="Networks the container is attached to.")
    # Volumes
    volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]] = Field(default=None, description="Volume mounts attached to the container.")
    # Environment variables
    environment: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Environment variables set inside the container.")
    env_file: Optional[Union[str, List[str]]] = Field(default=None, description="Files whose environment variables are loaded into the container.")
    # Command overrides
    command: Optional[Union[str, List[str]]] = Field(default=None, description="Override for the image's default command.")
    entrypoint: Optional[Union[str, List[str]]] = Field(default=None, description="Override for the image's entrypoint.")
    working_dir: Optional[str] = Field(default=None, description="Working directory used when running the container command.")
    user: Optional[str] = Field(default=None, description="User (name or UID) the container process runs as.")
    # Resource limits
    cpus: Optional[Union[str, float]] = Field(default=None, description="CPU quota expressed as a number of cores.")
    mem_limit: Optional[str] = Field(default=None, description="Maximum memory the container may use (e.g., '1G', '512M').")
    # Health check
    healthcheck: Optional[AppleContainerHealthCheck] = Field(default=None, description="Health check that determines whether the container is healthy.")
    # Miscellaneous
    labels: Optional[Dict[str, str]] = Field(default=None, description="Labels attached to the container as metadata.")
