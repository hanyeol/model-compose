from typing import Union, Optional, Dict, List
from pydantic import Field
from .common import CommonActionConfig

class ShellActionConfig(CommonActionConfig):
    command: Union[List[str], List[List[str]]] = Field(..., description="Shell command(s) to execute.")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the command.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables for the command.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum command runtime (e.g. '10s', '2m').")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input commands per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream stdout lines as produced instead of buffering until exit.")
