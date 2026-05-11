from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType

class GraphStoreDriver(str, Enum):
    NEO4J    = "neo4j"
    ARANGODB = "arangodb"

class CommonGraphStoreComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.GRAPH_STORE]
    driver: GraphStoreDriver = Field(..., description="Graph store backend driver.")
