from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonActionConfig

class VectorStoreActionMethod(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    SEARCH = "search"
    DELETE = "delete"

class VectorStoreFilterOperator(str, Enum):
    EQ     = "eq"
    NEQ    = "neq"
    GT     = "gt"
    GTE    = "gte"
    LT     = "lt"
    LTE    = "lte"
    IN     = "in"
    NOT_IN = "not-in"

class VectorStoreFilterCondition(BaseModel):
    field: str = Field(..., description="Metadata field the filter condition applies to.")
    operator: VectorStoreFilterOperator = Field(default=..., description="Comparison operator applied to the field value.")
    value: Any = Field(..., description="Value compared against the field.")

class CommonVectorStoreActionConfig(CommonActionConfig):
    method: VectorStoreActionMethod = Field(..., description="Vector store operation this action performs.")
    id_field: str = Field(default="id", description="Name of the field that identifies vectors in the store.")
    vector_field: str = Field(default="vector", description="Name of the field that stores vector embeddings.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of items processed per batch.")

    @classmethod
    def normalize_filter(cls, filter: Any) -> None:
        if isinstance(filter, dict):
            conditions = []
            for key, value in filter.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        conditions.append({ "field": key, "operator": subkey, "value": subvalue })
                else:
                    conditions.append({ "field": key, "operator": "eq", "value": value })
            return conditions
        return filter

class CommonVectorInsertActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.INSERT]
    vector: Union[List[float], List[List[float]], str] = Field(..., description="Vector or vectors inserted into the store.")
    vector_id: Optional[Union[Union[int, str], List[Union[int, str]], str]] = Field(default=None, description="ID or IDs assigned to the inserted vectors; auto-generated when omitted.")
    metadata: Optional[Union[Dict[str, Any], List[Dict[str, Any]], str]] = Field(default=None, description="Metadata attached to the inserted vectors.")

class CommonVectorUpdateActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.UPDATE]
    vector_id: Union[Union[int, str], List[Union[int, str]], str] = Field(..., description="ID or IDs of the vectors to update.")
    vector: Optional[Union[List[float], List[List[float]], str]] = Field(default=None, description="Replacement vector values for the updated entries.")
    metadata: Optional[Union[Dict[str, Any], List[Dict[str, Any]], str]] = Field(default=None, description="Metadata written to the updated vectors.")
    insert_if_not_exist: bool = Field(default=True, description="Whether a vector is inserted when the target ID does not yet exist.")

class CommonVectorSearchActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.SEARCH]
    query: Union[List[float], List[List[float]], str] = Field(..., description="Query vector or list of query vectors used for similarity search.")
    top_k: int = Field(default=10, description="Number of most similar vectors returned.")
    metric_type: Optional[str] = Field(default=None, description="Distance metric applied to the search (e.g., L2, IP, COSINE).")
    filter: Optional[Union[List[VectorStoreFilterCondition], str]] = Field(default=None, description="Metadata filter conditions applied to search candidates.")
    output_fields: Optional[List[str]] = Field(default=None, description="Metadata fields included with each search result.")

    @model_validator(mode="before")
    def inflate_filter(cls, values: Dict[str, Any]):
        filter = values.get("filter", None)
        if filter and not isinstance(filter, str):
            values["filter"] = cls.normalize_filter(filter)
        return values

class CommonVectorDeleteActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.DELETE]
    vector_id: Union[Union[int, str], List[Union[int, str]], str] = Field(..., description="ID or IDs of the vectors to delete.")
    filter: Optional[Union[List[VectorStoreFilterCondition], str]] = Field(default=None, description="Metadata filter conditions that select vectors to delete.")

    @model_validator(mode="before")
    def inflate_filter(cls, values: Dict[str, Any]):
        filter = values.get("filter", None)
        if filter and not isinstance(filter, str):
            values["filter"] = cls.normalize_filter(filter)
        return values
