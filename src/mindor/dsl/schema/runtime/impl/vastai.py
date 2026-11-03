from typing import Union, Literal, Optional, Dict
from pydantic import Field
from .common import RuntimeType, CommonRuntimeConfig

class VastaiRuntimeConfig(CommonRuntimeConfig):
    type: Literal[RuntimeType.VASTAI]

    api_key: str = Field(..., description="Vast.ai API key used to authenticate against the Vast.ai control plane.")

    # Instance spec
    gpu_type: str = Field(..., description="Vast.ai GPU catalog identifier (e.g., 'H100 SXM').")
    gpu_count: int = Field(default=1, description="Number of GPUs to attach to the instance.")
    cloud_type: Literal[ "DATACENTER", "VERIFIED", "UNVERIFIED", "ALL" ] = Field(default="VERIFIED", description="Vast.ai host tier used to allocate the instance.")
    max_price: Optional[float] = Field(default=None, description="Maximum acceptable hourly price in USD; offers above this are filtered out.")

    # Image
    image: Optional[str] = Field(default=None, description="Container image reference for the instance; defaults to the component standard CUDA image.")

    # Storage
    network_volume_id: Optional[int] = Field(default=None, description="Vast.ai network volume ID linked into the instance for persistent model weights.")
    volume_mount_path: str = Field(default="/workspace", description="Mount path inside the instance where the network volume is attached.")
    container_disk_gb: int = Field(default=20, description="Size of the instance's ephemeral container disk, in gigabytes.")

    # Networking
    worker_port: int = Field(default=8000, description="Port the component IPC worker binds inside the instance and exposes via the Vast.ai host port mapping.")

    # Env / command overrides
    environment: Optional[Dict[str, str]] = Field(default=None, description="Additional environment variables set inside the instance container.")

    # Lifecycle timeouts
    start_timeout: Union[str, int, float] = Field(default="30m", description="Maximum time to wait for the instance to reach RUNNING and the worker to report ready.")
    stop_timeout: Union[str, int, float] = Field(default="2m", description="Maximum time to wait for the instance to stop gracefully.")
    idle_timeout: Union[str, int, float] = Field(default="15m", description="Idle duration after which the instance is stopped to pause GPU billing; next request resumes it.")
