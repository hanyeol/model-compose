from typing import Literal, Optional, Dict
from enum import Enum
from pydantic import Field
from .common import RuntimeType, CommonRuntimeConfig

class IpcMethod(str, Enum):
    """IPC (Inter-Process Communication) method"""
    QUEUE       = "queue"
    UNIX_SOCKET = "unix-socket"
    NAMED_PIPE  = "named-pipe"
    TCP_SOCKET  = "tcp-socket"

class ProcessRuntimeConfig(CommonRuntimeConfig):
    """Process runtime configuration for running components in separate processes"""
    type: Literal[RuntimeType.PROCESS]

    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    working_dir: Optional[str] = Field(None, description="Working directory")

    start_timeout: str = Field(default="60s", description="Process start timeout")
    stop_timeout: str = Field(default="30s", description="Process stop timeout")

    ipc_method: IpcMethod = Field(default=IpcMethod.QUEUE, description="IPC method")
    socket_path: Optional[str] = Field(None, description="Unix socket path (for unix-socket)")
    pipe_name: Optional[str] = Field(None, description="Named pipe name (for named-pipe)")
    tcp_port: Optional[int] = Field(None, description="TCP port (for tcp-socket)")

    max_memory: Optional[str] = Field(None, description="Maximum memory limit")
    cpu_limit: Optional[float] = Field(None, description="CPU limit in cores")
