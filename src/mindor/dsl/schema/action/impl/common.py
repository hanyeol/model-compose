from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field

class CommonActionConfig(BaseModel):
    id: str = Field(default="__default__", description="ID of action.")
    output: Optional[Any] = Field(default=None, description="Output mapping to transform and extract specific values from the action result.")
    default: bool = Field(default=False, description="Whether this action should be used as the default.")
