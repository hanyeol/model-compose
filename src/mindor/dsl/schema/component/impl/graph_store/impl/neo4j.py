from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import Neo4jGraphStoreActionConfig
from .common import CommonGraphStoreComponentConfig, GraphStoreDriver

class Neo4jGraphStoreComponentConfig(CommonGraphStoreComponentConfig):
    driver: Literal[GraphStoreDriver.NEO4J]
    url: Optional[str] = Field(default=None, description="Neo4j connection URL (bolt:// or neo4j://).")
    host: str = Field(default="localhost", description="Neo4j server hostname or IP address.")
    port: int = Field(default=7687, ge=1, le=65535, description="Neo4j server port number.")
    protocol: Literal["bolt", "neo4j", "bolt+s", "neo4j+s", "bolt+ssc", "neo4j+ssc"] = Field(default="bolt", description="Neo4j connection protocol.")
    username: Optional[str] = Field(default=None, description="Username for authentication.")
    password: Optional[str] = Field(default=None, description="Password for authentication.")
    database: Optional[str] = Field(default=None, description="Target database name. Uses default database if not specified.")
    timeout: str = Field(default="30s", description="Client operation timeout.")
    actions: List[Neo4jGraphStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
