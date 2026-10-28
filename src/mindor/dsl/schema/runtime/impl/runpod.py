from typing import Union, Literal, Optional, Dict
from pydantic import Field
from .common import RuntimeType, CommonRuntimeConfig

class RunPodRuntimeConfig(CommonRuntimeConfig):
    type: Literal[RuntimeType.RUNPOD]

    api_key: str = Field(..., description="RunPod API key used to authenticate against the RunPod control plane.")

    # Pod spec
    gpu_type: str = Field(..., description="RunPod GPU catalog identifier (e.g., 'NVIDIA H100 PCIe').")
    gpu_count: int = Field(default=1, description="Number of GPUs to attach to the pod.")
    cloud_type: Literal[ "SECURE", "COMMUNITY", "ALL" ] = Field(default="SECURE", description="RunPod cloud tier used to allocate the pod.")
    data_center_id: Optional[str] = Field(default=None, description="RunPod data center ID; ignored when a network volume forces placement.")

    # Image
    image: Optional[str] = Field(default=None, description="Container image reference for the pod; defaults to the component standard CUDA image.")

    # Storage
    network_volume_id: Optional[str] = Field(default=None, description="RunPod network volume ID mounted into the pod for persistent model weights.")
    volume_mount_path: str = Field(default="/workspace", description="Mount path inside the pod where the network volume is attached.")
    container_disk_gb: int = Field(default=20, description="Size of the pod's ephemeral container disk, in gigabytes.")

    # Networking
    worker_port: int = Field(default=8000, description="Port the component IPC worker binds inside the pod and exposes via the RunPod HTTP proxy.")

    # Env / command overrides
    environment: Optional[Dict[str, str]] = Field(default=None, description="Additional environment variables set inside the pod container.")

    # Lifecycle timeouts
    start_timeout: Union[str, int, float] = Field(default="10m", description="Maximum time to wait for the pod to reach RUNNING and the worker to report ready.")
    stop_timeout: Union[str, int, float] = Field(default="2m", description="Maximum time to wait for the pod to stop gracefully.")
    idle_timeout: Union[str, int, float] = Field(default="15m", description="Idle duration after which the pod is stopped to pause GPU billing; next request resumes it.")
    terminate_on_down: bool = Field(default=False, description="Whether to terminate (fully delete) the pod on controller shutdown instead of only stopping it.")
