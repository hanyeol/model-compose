from typing import Union, Optional, Dict, List
from pydantic import Field
from .common import CommonActionConfig

class ShellActionConfig(CommonActionConfig):
    command: Union[List[str], List[List[str]]] = Field(..., description="Shell command or list of commands to execute.")
    working_dir: Optional[str] = Field(default=None, description="Working directory the command runs from.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables set for the command process.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the command to complete before failing.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input commands processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether stdout lines are emitted incrementally as they are produced.")
