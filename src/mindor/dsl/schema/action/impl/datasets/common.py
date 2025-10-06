from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ..common import CommonActionConfig

class DatasetsActionMethod(str, Enum):
    LOAD   = "load"
    CONCAT = "concat"
    SELECT = "select"
    FILTER = "filter"
    MAP    = "map"

class CommonDatasetsActionConfig(CommonActionConfig):
    method: DatasetsActionMethod = Field(..., description="Datasets operation method.")
