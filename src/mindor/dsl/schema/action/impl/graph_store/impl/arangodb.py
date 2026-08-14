from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import (
    CommonGraphQueryActionConfig,
    CommonGraphInsertActionConfig,
    CommonGraphUpdateActionConfig,
    CommonGraphDeleteActionConfig,
    CommonGraphTraverseActionConfig,
)

class ArangoDBGraphQueryActionConfig(CommonGraphQueryActionConfig):
    collection: Optional[str] = Field(default=None, description="Collection used as the query context.")

class ArangoDBGraphInsertActionConfig(CommonGraphInsertActionConfig):
    collection: Optional[str] = Field(default=None, description="Collection inserted nodes are written to.")
    edge_collection: Optional[str] = Field(default=None, description="Edge collection inserted relationships are written to.")
    graph: Optional[str] = Field(default=None, description="Named graph the insertion operates on.")

class ArangoDBGraphUpdateActionConfig(CommonGraphUpdateActionConfig):
    collection: Optional[str] = Field(default=None, description="Collection containing the elements being updated.")

class ArangoDBGraphDeleteActionConfig(CommonGraphDeleteActionConfig):
    collection: Optional[str] = Field(default=None, description="Collection containing the elements being deleted.")

class ArangoDBGraphTraverseActionConfig(CommonGraphTraverseActionConfig):
    graph: Optional[str] = Field(default=None, description="Named graph traversed by this action.")
    edge_collection: Optional[str] = Field(default=None, description="Edge collection traversed when no named graph is set.")

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
