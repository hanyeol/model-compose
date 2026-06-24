from typing import Union, Literal, Optional, Dict
from enum import Enum
from pydantic import Field
from .common import RuntimeType, CommonRuntimeConfig

class VirtualEnvDriver(str, Enum):
    PYTHON = "python"
    PYENV  = "pyenv"

class VirtualEnvRuntimeConfig(CommonRuntimeConfig):
    """VirtualEnv runtime configuration for running components inside an isolated Python venv"""
    type: Literal[RuntimeType.VIRTUALENV]

    driver: VirtualEnvDriver = Field(default=VirtualEnvDriver.PYTHON, description="Driver used to create the virtualenv.")
    path: Optional[str] = Field(default=None, description="Directory path of the virtualenv (relative to CWD).")
    python: Optional[str] = Field(default=None, description="Python version (pyenv driver only, e.g. '3.12.0').")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables for the worker subprocess.")

    start_timeout: Union[str, int, float] = Field(default="60s", description="Worker start timeout.")
    stop_timeout: Union[str, int, float] = Field(default="30s", description="Worker stop timeout.")
