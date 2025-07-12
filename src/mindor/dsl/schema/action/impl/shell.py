from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class ShellActionConfig(CommonActionConfig):
    command: List[str] = Field(..., description="The shell command to execute, as a list of arguments.")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the command.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the command.")
    timeout: Optional[float] = Field(default=None, description="Maximum time allowed for the command to run, in seconds.")
