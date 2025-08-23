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
    field: str = Field(..., description="")
    operator: VectorStoreFilterOperator = Field(default=..., description="")
    value: Any = Field(..., description="")

class CommonVectorStoreActionConfig(CommonActionConfig):
    method: VectorStoreActionMethod = Field(..., description="")
    id_field: str = Field(default="id", description="")
    vector_field: str = Field(default="vector", description="")
    batch_size: Union[int, str] = Field(default=0, description="Number of items to process in a single batch.")

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
    vector: Union[Union[List[float], List[List[float]]], str] = Field(..., description="Vector to insert.")
    vector_id: Optional[Union[Union[Union[int, str], List[Union[int, str]]], str]] = Field(default=None, description="ID of vector to insert.")
    metadata: Optional[Union[Union[Dict[str, Any], List[Dict[str, Any]]], str]] = Field(default=None, description="Metadata for vector.")

class CommonVectorUpdateActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.UPDATE]
    vector_id: Union[Union[Union[int, str], List[Union[int, str]]], str] = Field(..., description="ID of vector to update.")
    vector: Optional[Union[Union[List[float], List[List[float]]], str]] = Field(default=None, description="New vector to replace.")
    metadata: Optional[Union[Union[Dict[str, Any], List[Dict[str, Any]]], str]] = Field(default=None, description="Updated metadata for vector.")
    insert_if_not_exist: bool = Field(default=True, description="")

class CommonVectorSearchActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.SEARCH]
    query: Union[List[float], str] = Field(..., description="Query vector for similarity search.")
    top_k: int = Field(default=10, description="Number of top similar vectors to return.")
    metric_type: Optional[str] = Field(default=None, description="Distance metric (L2, IP, COSINE, etc.)")
    filter: Optional[Union[Union[str, List[VectorStoreFilterCondition]], str]] = Field(default=None, description="")
    output_fields: Optional[List[str]] = Field(default=None, description="")

    @model_validator(mode="before")
    def inflate_filter(cls, values: Dict[str, Any]):
        filter = values.get("filter", None)
        if filter and not isinstance(filter, str):
            values["filter"] = cls.normalize_filter(filter)
        return values

class CommonVectorDeleteActionConfig(CommonVectorStoreActionConfig):
    method: Literal[VectorStoreActionMethod.DELETE]
    vector_id: Union[Union[Union[int, str], List[Union[int, str]]], str] = Field(..., description="ID of vector to remove.")
    filter: Optional[Union[Union[str, List[VectorStoreFilterCondition], str]]] = Field(default=None, description="")

    @model_validator(mode="before")
    def inflate_filter(cls, values: Dict[str, Any]):
        filter = values.get("filter", None)
        if filter and not isinstance(filter, str):
            values["filter"] = cls.normalize_filter(filter)
        return values
