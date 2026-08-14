from typing import Union, Literal, Optional, Dict
from pydantic import Field
from .common import RuntimeType, CommonRuntimeConfig

class ProcessRuntimeConfig(CommonRuntimeConfig):
    """Process runtime configuration for running components in separate processes"""
    type: Literal[RuntimeType.PROCESS]

    working_dir: Optional[str] = Field(None, description="Working directory in which the worker process is launched.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables passed to the worker process.")

    max_memory: Optional[str] = Field(None, description="Maximum memory the worker process may use (e.g., '512m', '2g').")
    cpu_limit: Optional[float] = Field(None, description="Maximum CPU allocation for the worker process, in cores.")

    start_timeout: Union[str, int, float] = Field(default="60s", description="Maximum time to wait for the worker process to start and report ready.")
    stop_timeout: Union[str, int, float] = Field(default="30s", description="Maximum time to wait for the worker process to stop gracefully before being killed.")
