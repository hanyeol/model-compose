from typing import Union, Optional, Dict, List
from pydantic import Field
from .common import CommonActionConfig

class ShellActionConfig(CommonActionConfig):
    command: Union[List[str], List[List[str]]] = Field(..., description="The shell command(s) to execute. A single command is given as a list of arguments; a batch of commands is given as a list of such lists.")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the command.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the command.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time allowed for the command to run (e.g. '10s', '2m').")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input commands to process in a single batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream stdout lines as they are produced instead of buffering until the command exits.")
