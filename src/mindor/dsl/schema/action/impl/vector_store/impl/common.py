from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class VectorStoreActionType(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    SEARCH = "search"
    REMOVE = "remove"

class CommonVectorStoreActionConfig(CommonActionConfig):
    type: VectorStoreActionType = Field(..., description="")

class CommonVectorInsertActionConfig(CommonVectorStoreActionConfig):
    type: Literal[VectorStoreActionType.INSERT]

class CommonVectorUpdateActionConfig(CommonVectorStoreActionConfig):
    type: Literal[VectorStoreActionType.UPDATE]

class CommonVectorSearchActionConfig(CommonVectorStoreActionConfig):
    type: Literal[VectorStoreActionType.SEARCH]

class CommonVectorRemoveActionConfig(CommonVectorStoreActionConfig):
    type: Literal[VectorStoreActionType.REMOVE]
