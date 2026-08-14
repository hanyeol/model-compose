from typing import Union, Literal, Optional, Dict, List
from pydantic import BaseModel, Field

class DockerBuildConfig(BaseModel):
    context: Optional[str] = Field(default=None, description="Filesystem path used as the Docker build context.")
    dockerfile: Optional[str] = Field(default=None, description="Path to the Dockerfile, relative to the build context.")
    args: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Build-time arguments passed to the Dockerfile.")
    target: Optional[str] = Field(default=None, description="Target stage to build in a multi-stage Dockerfile.")
    cache_from: Optional[List[str]] = Field(default=None, description="Images consulted as sources for the build cache.")
    labels: Optional[Dict[str, str]] = Field(default=None, description="Labels applied to the built image.")
    network: Optional[str] = Field(default=None, description="Network mode used while executing the build.")
    pull: Optional[bool] = Field(default=None, description="Whether to always pull newer versions of base images before building.")
    shm_size: Optional[str] = Field(default=None, description="Shared memory size for the build container (e.g., '2gb').")

class DockerPortConfig(BaseModel):
    container_port: int = Field(..., description="TCP/UDP port exposed inside the container.")
    host_port: Optional[int] = Field(default=None, description="Port on the host that maps to the container port.")
    host_ip: Optional[str] = Field(default=None, description="Host IP address the published port binds to (e.g., 127.0.0.1); binds to all interfaces when unset.")
    protocol: Optional[Literal["tcp", "udp"]] = Field(default="tcp", description="Transport protocol used for the port mapping.")

class DockerVolumeOptionsConfig(BaseModel):
    nocopy: bool = Field(default=False, description="Whether to skip copying data from the container path when creating the volume.")
    labels: Optional[Dict[str, str]] = Field(default=None, description="Labels attached to the volume as metadata.")

class DockerTmpfsOptionsConfig(BaseModel):
    size: Optional[int] = Field(default=None, description="Size of the tmpfs mount, in bytes.")
    mode: Optional[int] = Field(default=None, description="Octal file mode applied to the tmpfs mount (e.g., 1777).")

class DockerVolumeConfig(BaseModel):
    type: Optional[Literal["bind", "volume", "tmpfs"]] = Field(default=None, description="Type of mount (e.g., bind, volume, tmpfs).")
    target: str = Field(..., description="Mount path inside the container.")
    source: Optional[str] = Field(default=None, description="Host path (for bind mounts) or named volume (for volume mounts).")
    read_only: Optional[bool] = Field(default=None, description="Whether the mount is read-only.")
    bind: Optional[Dict[str, Union[str, bool]]] = Field(default=None, description="Additional options applied to bind mounts.")
    volume: Optional[DockerVolumeOptionsConfig] = Field(default=None, description="Additional options applied to named volume mounts.")
    tmpfs: Optional[DockerTmpfsOptionsConfig] = Field(default=None, description="Additional options applied to tmpfs mounts.")

class DockerHealthCheck(BaseModel):
    test: Union[str, List[str]] = Field(..., description="Command executed inside the container to determine health.")
    interval: Union[str, int, float] = Field(default="30s", description="Time between health check invocations.")
    timeout: Union[str, int, float] = Field(default="30s", description="Maximum time a single health check may run before being considered failed.")
    max_retry_count: Optional[int] = Field(default=3, description="Consecutive failures required before the container is marked unhealthy.")
    start_period: Optional[Union[str, int, float]] = Field(default="0s", description="Grace period after startup before health checks begin counting failures.")

class DockerContainerConfig(BaseModel):
    # Image or build
    image: Optional[str] = Field(default=None, description="Docker image reference with optional tag. Mutually exclusive with `build`.")
    build: Optional[DockerBuildConfig] = Field(default=None, description="Settings for building the image locally instead of pulling.")
    # Container identity
    container_name: Optional[str] = Field(default=None, description="Name assigned to the container.")
    hostname: Optional[str] = Field(default=None, description="Hostname reported from inside the container.")
    # Networking
    ports: Optional[List[Union[str, int, DockerPortConfig]]] = Field(default=None, description="Port mappings between the host and the container.")
    networks: Optional[List[str]] = Field(default_factory=list, description="Docker networks the container is attached to.")
    extra_hosts: Optional[Dict[str, str]] = Field(default=None, description="Additional entries added to the container's /etc/hosts.")
    # Volumes
    volumes: Optional[List[Union[str, DockerVolumeConfig]]] = Field(default=None, description="Volume mounts attached to the container.")
    # GPU
    gpus: Optional[Union[str, int]] = Field(default=None, description="GPUs exposed to the container; use 'all' or a count (e.g., 1).")
    # Environment variables
    environment: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default=None, description="Environment variables set inside the container.")
    env_file: Optional[Union[str, List[str]]] = Field(default=None, description="Files whose environment variables are loaded into the container.")
    # Command overrides
    command: Optional[Union[str, List[str]]] = Field(default=None, description="Override for the image's default command.")
    entrypoint: Optional[Union[str, List[str]]] = Field(default=None, description="Override for the image's entrypoint.")
    working_dir: Optional[str] = Field(default=None, description="Working directory used when running the container command.")
    user: Optional[str] = Field(default=None, description="User (name or UID) the container process runs as.")
    # Resource limits
    shm_size: Optional[str] = Field(default=None, description="Shared memory size available to the container (e.g., '2gb').")
    mem_limit: Optional[str] = Field(default=None, description="Maximum memory the container may use (e.g., '1g', '512m').")
    memswap_limit: Optional[str] = Field(default=None, description="Combined memory and swap limit for the container.")
    cpus: Optional[Union[str, float]] = Field(default=None, description="CPU quota expressed as a number of cores.")
    cpu_shares: Optional[int] = Field(default=None, description="Relative CPU scheduling weight compared to other containers.")
    # Restart policy and health checks
    restart: Literal[ "no", "always", "on-failure", "unless-stopped" ] = Field(default="no", description="Restart policy applied to the container by Docker.")
    healthcheck: Optional[DockerHealthCheck] = Field(default=None, description="Health check that determines whether the container is healthy.")
    # Miscellaneous
    labels: Optional[Dict[str, str]] = Field(default=None, description="Labels attached to the container as metadata.")
    privileged: Optional[bool] = Field(default=None, description="Whether the container runs in privileged mode.")
    security_opt: Optional[List[str]] = Field(default=None, description="Security options passed through to the container runtime.")
