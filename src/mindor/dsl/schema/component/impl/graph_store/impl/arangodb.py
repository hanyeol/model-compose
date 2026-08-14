from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import ArangoDBGraphStoreActionConfig
from .common import CommonGraphStoreComponentConfig, GraphStoreDriver

class ArangoDBGraphStoreComponentConfig(CommonGraphStoreComponentConfig):
    driver: Literal[GraphStoreDriver.ARANGODB]
    url: Optional[str] = Field(default=None, description="Full ArangoDB connection URL (e.g., http://host:port). Mutually exclusive with `host`.")
    host: str = Field(default="localhost", description="Hostname or IP address of the ArangoDB server.")
    port: int = Field(default=8529, ge=1, le=65535, description="TCP port the ArangoDB server listens on.")
    protocol: Literal[ "http", "https" ] = Field(default="http", description="Scheme used to connect to ArangoDB.")
    username: Optional[str] = Field(default=None, description="Username used to authenticate with ArangoDB.")
    password: Optional[str] = Field(default=None, description="Password used to authenticate with ArangoDB.")
    database: str = Field(default="_system", description="Target ArangoDB database name.")
    timeout: Union[str, int, float] = Field(default="30s", description="Maximum seconds to wait for an ArangoDB operation before failing.")
    actions: List[ArangoDBGraphStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
