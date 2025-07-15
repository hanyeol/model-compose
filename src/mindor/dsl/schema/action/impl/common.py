from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field

class CommonActionConfig(BaseModel):
    output: Optional[Any] = Field(default=None)
    default: bool = Field(default=False)
