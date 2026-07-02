from typing import Union, Literal, Optional, Dict
from pydantic import Field
from .common import RuntimeType, CommonRuntimeConfig

class ProcessRuntimeConfig(CommonRuntimeConfig):
    """Process runtime configuration for running components in separate processes"""
    type: Literal[RuntimeType.PROCESS]

    working_dir: Optional[str] = Field(None, description="Working directory")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")

    max_memory: Optional[str] = Field(None, description="Maximum memory limit")
    cpu_limit: Optional[float] = Field(None, description="CPU limit in cores")

    start_timeout: Union[str, int, float] = Field(default="60s", description="Process start timeout")
    stop_timeout: Union[str, int, float] = Field(default="30s", description="Process stop timeout")
