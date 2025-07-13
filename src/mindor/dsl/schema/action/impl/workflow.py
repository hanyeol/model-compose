from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class WorkflowActionConfig(CommonActionConfig):
    workflow: str = Field(default="__default__", description="The workflow to run. Defaults to '__default__'.")
    input: Optional[Any] = Field(default=None, description="Input data supplied to the workflow. Accepts any type.")
