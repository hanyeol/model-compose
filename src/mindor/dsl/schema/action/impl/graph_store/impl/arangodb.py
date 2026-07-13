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
    collection: Optional[str] = Field(default=None, description="Target collection for query context.")

class ArangoDBGraphInsertActionConfig(CommonGraphInsertActionConfig):
    collection: Optional[str] = Field(default=None, description="Target collection for node insertion.")
    edge_collection: Optional[str] = Field(default=None, description="Target edge collection for relationship insertion.")
    graph: Optional[str] = Field(default=None, description="Named graph to operate on.")

class ArangoDBGraphUpdateActionConfig(CommonGraphUpdateActionConfig):
    collection: Optional[str] = Field(default=None, description="Target collection for update.")

class ArangoDBGraphDeleteActionConfig(CommonGraphDeleteActionConfig):
    collection: Optional[str] = Field(default=None, description="Target collection for deletion.")

class ArangoDBGraphTraverseActionConfig(CommonGraphTraverseActionConfig):
    graph: Optional[str] = Field(default=None, description="Named graph to traverse.")
    edge_collection: Optional[str] = Field(default=None, description="Edge collection to traverse when not using a named graph.")

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
