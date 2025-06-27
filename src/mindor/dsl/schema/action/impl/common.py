from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field

class CommonActionConfig(BaseModel):
    output: Optional[Any] = None
    default: bool = False
