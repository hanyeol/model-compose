from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import (
    CommonGraphQueryActionConfig,
    CommonGraphInsertActionConfig,
    CommonGraphUpdateActionConfig,
    CommonGraphDeleteActionConfig,
    CommonGraphTraverseActionConfig
)

class Neo4jGraphQueryActionConfig(CommonGraphQueryActionConfig):
    database: Optional[str] = Field(default=None, description="Target Neo4j database for this query.")

class Neo4jGraphInsertActionConfig(CommonGraphInsertActionConfig):
    database: Optional[str] = Field(default=None, description="Target Neo4j database for this operation.")

class Neo4jGraphUpdateActionConfig(CommonGraphUpdateActionConfig):
    database: Optional[str] = Field(default=None, description="Target Neo4j database for this operation.")

class Neo4jGraphDeleteActionConfig(CommonGraphDeleteActionConfig):
    database: Optional[str] = Field(default=None, description="Target Neo4j database for this operation.")

class Neo4jGraphTraverseActionConfig(CommonGraphTraverseActionConfig):
    database: Optional[str] = Field(default=None, description="Target Neo4j database for this operation.")

Neo4jGraphStoreActionConfig = Annotated[
    Union[
        Neo4jGraphQueryActionConfig,
        Neo4jGraphInsertActionConfig,
        Neo4jGraphUpdateActionConfig,
        Neo4jGraphDeleteActionConfig,
        Neo4jGraphTraverseActionConfig
    ],
    Field(discriminator="method")
]
