from typing import Union, Literal, Optional, Dict, List, Any
from pydantic import Field
from .common import CommonSystemConfig
from .types import SystemType
from mindor.dsl.schema.runtime.impl.docker import (
    DockerBuildConfig,
    DockerPortConfig,
    DockerVolumeConfig,
    DockerHealthCheck,
)

class DockerSystemConfig(CommonSystemConfig):
    type: Literal[SystemType.DOCKER] = Field(default=SystemType.DOCKER, description="Docker system type.")
    # Image or build
    image: Optional[str] = Field(default=None, description="Docker image name with optional tag.")
    build: Optional[DockerBuildConfig] = Field(default=None, description="Build configuration for building image locally.")
    # Container identity
    container_name: Optional[str] = Field(default=None, description="Name of the container.")
    hostname: Optional[str] = Field(default=None, description="Hostname inside the container.")
    # Networking
    ports: Optional[List[Union[str, int, DockerPortConfig]]] = Field(default=None, description="Port mappings.")
    networks: Optional[List[str]] = Field(default_factory=list, description="Networks to attach the container to.")
    extra_hosts: Optional[Dict[str, str]] = Field(default=None, description="Extra hosts to add to /etc/hosts.")
    # Volumes
    volumes: Optional[List[Union[str, DockerVolumeConfig]]] = Field(default=None, description="Volume mounts.")
    # GPU
    gpus: Optional[Union[str, int]] = Field(default=None, description="GPU devices to expose. Use 'all' for all GPUs or a count (e.g. 1).")
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
    restart: str = Field(default="no", description="Restart policy.")
    healthcheck: Optional[DockerHealthCheck] = Field(default=None, description="Health check configuration.")
    # Miscellaneous
    labels: Optional[Dict[str, str]] = Field(default=None, description="Container labels.")
    privileged: Optional[bool] = Field(default=None, description="Run container in privileged mode.")
    security_opt: Optional[List[str]] = Field(default=None, description="Security options.")
    # System-specific
    wait: bool = Field(default=True, description="Whether to wait for the container to be ready before proceeding.")
    wait_timeout: Optional[str] = Field(default="60s", description="Timeout for waiting for container to be ready.")
