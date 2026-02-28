from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ChromaVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class ChromaVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.CHROMA]
    mode: Literal[ "local", "server" ] = Field(default="local", description="Run Chroma locally or connect to a server.")
    storage_dir: str = Field(default="./chroma", description="Local storage path.")
    host: str = Field(default="localhost", description="Chroma server hostname or IP address.")
    port: int = Field(default=8000, ge=1, le=65535, description="Chroma server port number.")
    protocol: Literal[ "http", "https" ] = Field(default="http", description="Connection protocol.")
    tenant: Optional[str] = Field(default=None, description="Target tenant name.")
    database: Optional[str] = Field(default=None, description="Target database name.")
    timeout: str = Field(default="30s", description="Client operation timeout.")
    actions: List[ChromaVectorStoreActionConfig] = Field(default_factory=list)
