from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import Neo4jGraphStoreActionConfig
from .common import CommonGraphStoreComponentConfig, GraphStoreDriver

class Neo4jGraphStoreComponentConfig(CommonGraphStoreComponentConfig):
    driver: Literal[GraphStoreDriver.NEO4J]
    uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI (bolt:// or neo4j://).")
    username: Optional[str] = Field(default=None, description="Username for authentication.")
    password: Optional[str] = Field(default=None, description="Password for authentication.")
    database: Optional[str] = Field(default=None, description="Target database name. Uses default database if not specified.")
    timeout: str = Field(default="30s", description="Client operation timeout.")
    actions: List[Neo4jGraphStoreActionConfig] = Field(default_factory=list)
