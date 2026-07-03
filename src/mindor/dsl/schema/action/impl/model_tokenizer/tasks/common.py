from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class ModelTokenizerMethod(str, Enum):
    ENCODE = "encode"
    DECODE = "decode"
    COUNT  = "count"

class CommonModelTokenizerActionConfig(CommonActionConfig):
    method: ModelTokenizerMethod = Field(..., description="Tokenizer method.")
