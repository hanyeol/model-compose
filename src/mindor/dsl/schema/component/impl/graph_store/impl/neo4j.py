from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import Neo4jGraphStoreActionConfig
from .common import CommonGraphStoreComponentConfig, GraphStoreDriver

class Neo4jGraphStoreComponentConfig(CommonGraphStoreComponentConfig):
    driver: Literal[GraphStoreDriver.NEO4J]
    url: Optional[str] = Field(default=None, description="Full Neo4j connection URL (e.g., bolt://host:port or neo4j://host:port). Mutually exclusive with `host`.")
    host: str = Field(default="localhost", description="Hostname or IP address of the Neo4j server.")
    port: int = Field(default=7687, ge=1, le=65535, description="TCP port the Neo4j server listens on.")
    protocol: Literal[ "bolt", "neo4j", "bolt+s", "neo4j+s", "bolt+ssc", "neo4j+ssc" ] = Field(default="bolt", description="Scheme used to connect to Neo4j.")
    username: Optional[str] = Field(default=None, description="Username used to authenticate with Neo4j.")
    password: Optional[str] = Field(default=None, description="Password used to authenticate with Neo4j.")
    database: Optional[str] = Field(default=None, description="Target Neo4j database name; the server default is used when unset.")
    timeout: Union[str, int, float] = Field(default="30s", description="Maximum seconds to wait for a Neo4j operation before failing.")
    actions: List[Neo4jGraphStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
