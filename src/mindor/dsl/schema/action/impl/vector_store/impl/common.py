from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class VectorStoreActionMethod(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    SEARCH = "search"
    REMOVE = "remove"

class CommonVectorStoreActionConfig(CommonActionConfig):
    method: VectorStoreActionMethod = Field(..., description="")
    collection_name: str = Field(..., description="Name of the Milvus collection to store vectors.")
    vector_field: str = Field(default="vector", description="")

class CommonVectorInsertActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.INSERT]
    vectors: Union[str, List[List[float]]] = Field(..., description="List of vectors to insert.")
    ids: Optional[Union[str, List[str]]] = Field(default=None, description="Custom IDs for vectors.")
    metadata: Optional[Union[str, List[Dict[str, Any]]]] = Field(default=None, description="Metadata for each vector.")

class CommonVectorUpdateActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.UPDATE]

class CommonVectorSearchActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.SEARCH]

class CommonVectorRemoveActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.REMOVE]
