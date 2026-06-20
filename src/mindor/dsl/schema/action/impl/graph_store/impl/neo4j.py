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
    pass

class Neo4jGraphInsertActionConfig(CommonGraphInsertActionConfig):
    pass

class Neo4jGraphUpdateActionConfig(CommonGraphUpdateActionConfig):
    pass

class Neo4jGraphDeleteActionConfig(CommonGraphDeleteActionConfig):
    pass

class Neo4jGraphTraverseActionConfig(CommonGraphTraverseActionConfig):
    pass

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
