from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class CommonModelActionConfig(CommonActionConfig):
    stream: Optional[bool] = Field(default=None, description="Whether to enable streaming responses for inference.")
