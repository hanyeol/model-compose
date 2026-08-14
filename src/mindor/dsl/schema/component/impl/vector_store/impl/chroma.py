from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ChromaVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class ChromaVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.CHROMA]
    mode: Literal[ "local", "server" ] = Field(default="local", description="Whether Chroma runs embedded locally or connects to a remote server.")
    storage_dir: str = Field(default="./chroma", description="Directory where Chroma persists data when running in local mode.")
    host: str = Field(default="localhost", description="Hostname or IP address of the Chroma server.")
    port: int = Field(default=8000, ge=1, le=65535, description="TCP port the Chroma server listens on.")
    protocol: Literal[ "http", "https" ] = Field(default="http", description="Scheme used to connect to the Chroma server.")
    tenant: Optional[str] = Field(default=None, description="Target Chroma tenant name.")
    database: Optional[str] = Field(default=None, description="Target Chroma database name.")
    timeout: Union[str, int, float] = Field(default="30s", description="Maximum seconds to wait for a Chroma operation before failing.")
    actions: List[ChromaVectorStoreActionConfig] = Field(default_factory=list)
