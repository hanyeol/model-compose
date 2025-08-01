from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import RuntimeType, CommonRuntimeConfig

class DockerBuildConfig(BaseModel):
    context: Optional[str] = Field(default=None, description="Build context path.")
    dockerfile: Optional[str] = Field(default=None, description="Path to Dockerfile relative to context.")
    args: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Build arguments as key-value pairs.")
    target: Optional[str] = Field(default=None, description="Target build stage in multi-stage builds.")
    cache_from: Optional[List[str]] = Field(default=None, description="Images to use for build cache resolution.")
    labels: Optional[Dict[str, str]] = Field(default=None, description="Image labels to apply at build time.")
    network: Optional[str] = Field(default=None, description="Network mode used during build.")
    pull: Optional[bool] = Field(default=None, description="Always pull newer versions of base images.")
    shm_size: Optional[str] = Field(default=None, description="Shared memory size.")

class DockerPortConfig(BaseModel):
    target: int = Field(..., description="Port exposed by the container.")
    published: Optional[int] = Field(default=None, description="Host port to publish.")
    protocol: Optional[Literal[ "tcp", "udp" ]] = Field(default="tcp", description="Protocol.")
    mode: Optional[Literal[ "host", "ingress" ]] = Field(default=None, description="Publishing mode.")

class DockerVolumeConfig(BaseModel):
    type: Optional[Literal[ "bind", "volume", "tmpfs" ]] = Field(default=None, description="Volume type.")
    target: str = Field(..., description="Target path inside the container.")
    source: Optional[str] = Field(default=None, description="Source path or volume name on the host.")
    read_only: Optional[bool] = Field(default=None, description="Mount as read-only.")
    bind: Optional[Dict[str, Union[str, bool]]] = Field(default=None, description="Bind options.")
    volume: Optional[Dict[str, str]] = Field(default=None, description="Volume options.")
    tmpfs: Optional[Dict[str, Union[str, int]]] = Field(default=None, description="tmpfs mount options.")

class DockerHealthCheck(BaseModel):
    test: Union[str, List[str]] = Field(..., description="Health check command.")
    interval: Optional[str] = Field(default="30s", description="Time between checks.")
    timeout: Optional[str] = Field(default="30s", description="Timeout for each check.")
    retries: Optional[int] = Field(default=3, description="Number of failures before marking as unhealthy.")
    start_period: Optional[str] = Field(default="0s", description="Startup grace period before checks start.")

class DockerRuntimeConfig(CommonRuntimeConfig):
    type: Literal[RuntimeType.DOCKER]
    # Image or build
    image: Optional[str] = Field(default=None, description="Docker image name with optional tag.")
    build: Optional[DockerBuildConfig] = Field(default=None, description="Build configuration for building image locally.")
    # Container identity
    container_name: Optional[str] = Field(default=None, description="Name of the container.")
    hostname: Optional[str] = Field(default=None, description="Hostname inside the container.")
    # Networking
    ports: Optional[List[Union[str, int, DockerPortConfig]]] = Field(default=None, description="Port mappings.")
    networks: Optional[List[str]] = Field(default_factory=list, description="Networks to attach the container to.")
    # Volumes
    volumes: Optional[List[Union[str, DockerVolumeConfig]]] = Field(default=None, description="Volume mounts.")
    # Environment variables
    environment: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Environment variables.")
    env_file: Optional[Union[str, List[str]]] = Field(default=None, description="Environment files.")
    # Command overrides
    command: Optional[Union[str, List[str]]] = Field(default=None, description="Override the default command.")
    entrypoint: Optional[Union[str, List[str]]] = Field(default=None, description="Override the entrypoint.")
    working_dir: Optional[str] = Field(default=None, description="Working directory inside the container.")
    user: Optional[str] = Field(default=None, description="User to run the container as.")
    # Resource limits
    mem_limit: Optional[str] = Field(default=None, description="Memory limit.")
    memswap_limit: Optional[str] = Field(default=None, description="Total memory + swap limit.")
    cpus: Optional[Union[str, float]] = Field(default=None, description="CPU quota.")
    cpu_shares: Optional[int] = Field(default=None, description="Relative CPU weight.")
    # Restart policy and health checks
    restart: Literal[ "no", "always", "on-failure", "unless-stopped" ] = Field(default="no", description="Restart policy.")
    healthcheck: Optional[DockerHealthCheck] = Field(default=None, description="Health check configuration.")
    # Miscellaneous
    labels: Optional[Dict[str, str]] = Field(default=None, description="Container labels.")
    logging: Optional[Dict[str, Union[str, Dict]]] = Field(default=None, description="Logging configuration.")
    privileged: Optional[bool] = Field(default=None, description="Run container in privileged mode.")
    security_opt: Optional[List[str]] = Field(default=None, description="Security options.")
