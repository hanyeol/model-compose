from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, field_validator
from pydantic import model_validator
from .common import (
    CommonGraphQueryActionConfig,
    CommonGraphInsertActionConfig,
    CommonGraphUpdateActionConfig,
    CommonGraphDeleteActionConfig,
    CommonGraphTraverseActionConfig,
    _validate_identifier,
)

class ArangoDBGraphQueryActionConfig(CommonGraphQueryActionConfig):
    collection: Optional[str] = Field(default=None, description="Target collection for query context.")

    @field_validator("collection")
    @classmethod
    def validate_collection(cls, v):
        return _validate_identifier(v) if v else v

class ArangoDBGraphInsertActionConfig(CommonGraphInsertActionConfig):
    collection: Optional[str] = Field(default=None, description="Target collection for node insertion.")
    edge_collection: Optional[str] = Field(default=None, description="Target edge collection for relationship insertion.")
    graph: Optional[str] = Field(default=None, description="Named graph to operate on.")

    @field_validator("collection", "edge_collection", "graph")
    @classmethod
    def validate_identifiers(cls, v):
        return _validate_identifier(v) if v else v

class ArangoDBGraphUpdateActionConfig(CommonGraphUpdateActionConfig):
    collection: Optional[str] = Field(default=None, description="Target collection for update.")

    @field_validator("collection")
    @classmethod
    def validate_collection(cls, v):
        return _validate_identifier(v) if v else v

class ArangoDBGraphDeleteActionConfig(CommonGraphDeleteActionConfig):
    collection: Optional[str] = Field(default=None, description="Target collection for deletion.")

    @field_validator("collection")
    @classmethod
    def validate_collection(cls, v):
        return _validate_identifier(v) if v else v

class ArangoDBGraphTraverseActionConfig(CommonGraphTraverseActionConfig):
    graph: Optional[str] = Field(default=None, description="Named graph to traverse.")
    edge_collection: Optional[str] = Field(default=None, description="Edge collection to traverse if not using named graph.")

    @field_validator("graph", "edge_collection")
    @classmethod
    def validate_identifiers(cls, v):
        return _validate_identifier(v) if v else v

ArangoDBGraphStoreActionConfig = Annotated[
    Union[
        ArangoDBGraphQueryActionConfig,
        ArangoDBGraphInsertActionConfig,
        ArangoDBGraphUpdateActionConfig,
        ArangoDBGraphDeleteActionConfig,
        ArangoDBGraphTraverseActionConfig
    ],
    Field(discriminator="method")
]
