from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ArangoDBGraphStoreActionConfig
from .common import CommonGraphStoreComponentConfig, GraphStoreDriver

class ArangoDBGraphStoreComponentConfig(CommonGraphStoreComponentConfig):
    driver: Literal[GraphStoreDriver.ARANGODB]
    host: str = Field(default="localhost", description="ArangoDB server hostname or IP address.")
    port: int = Field(default=8529, ge=1, le=65535, description="ArangoDB server port number.")
    protocol: Literal["http", "https"] = Field(default="http", description="Connection protocol.")
    username: Optional[str] = Field(default=None, description="Username for authentication.")
    password: Optional[str] = Field(default=None, description="Password for authentication.")
    database: str = Field(default="_system", description="Target database name.")
    timeout: str = Field(default="30s", description="Client operation timeout.")
    actions: List[ArangoDBGraphStoreActionConfig] = Field(default_factory=list)
