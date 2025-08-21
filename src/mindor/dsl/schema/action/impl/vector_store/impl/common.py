from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class VectorStoreActionMethod(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    SEARCH = "search"
    DELETE = "delete"

class CommonVectorStoreActionConfig(CommonActionConfig):
    method: VectorStoreActionMethod = Field(..., description="")
    id_field: str = Field(default="id", description="")
    vector_field: str = Field(default="vector", description="")

class CommonVectorInsertActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.INSERT]
    vector: Union[str, Union[List[float], List[List[float]]]] = Field(..., description="Vector to insert.")
    vector_id: Optional[Union[str, Union[Union[int, str], List[Union[int, str]]]]] = Field(default=None, description="ID of vector to insert.")
    metadata: Optional[Union[str, Union[Dict[str, Any], List[Dict[str, Any]]]]] = Field(default=None, description="Metadata for vector.")

class CommonVectorUpdateActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.UPDATE]
    vector_id: Union[str, Union[Union[int, str], List[Union[int, str]]]] = Field(..., description="ID of vector to update.")
    vector: Optional[Union[str, Union[List[float], List[List[float]]]]] = Field(default=None, description="New vector to replace.")
    metadata: Optional[Union[str, Union[Dict[str, Any], List[Dict[str, Any]]]]] = Field(default=None, description="Updated metadata for vector.")
    insert_if_not_exist: bool = Field(default=True, description="")

class CommonVectorSearchActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.SEARCH]
    query: Union[str, List[float]] = Field(..., description="Query vector for similarity search.")
    top_k: int = Field(default=10, description="Number of top similar vectors to return.")
    metric_type: Optional[str] = Field(default=None, description="Distance metric (L2, IP, COSINE, etc.)")
    filter: Optional[Union[str, Union[str, Dict[str, Any]]]] = Field(default=None, description="")
    output_fields: Optional[Union[str, List[str]]] = Field(default=None, description="")

class CommonVectorDeleteActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.DELETE]
    vector_id: Union[str, Union[Union[int, str], List[Union[int, str]]]] = Field(..., description="ID of vector to remove.")
