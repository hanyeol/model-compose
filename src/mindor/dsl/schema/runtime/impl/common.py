from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .types import RuntimeType

class CommonRumtimeConfig(BaseModel):
    type: RuntimeType
