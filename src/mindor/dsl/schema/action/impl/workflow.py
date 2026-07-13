from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class WorkflowActionConfig(CommonActionConfig):
    workflow: str = Field(default="__default__", description="Workflow to run.")
    input: Optional[Any] = Field(default=None, description="Input data for the workflow. Accepts any type.")
