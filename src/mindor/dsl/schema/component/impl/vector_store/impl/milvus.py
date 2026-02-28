from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import MilvusVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class MilvusVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.MILVUS]
    endpoint: Optional[str] = Field(default=None, description="Milvus server endpoint URL.")
    host: str = Field(default="localhost", description="Milvus server hostname or IP address.")
    port: int = Field(default=19530, ge=1, le=65535, description="Milvus server port number.")
    protocol: Literal[ "http", "https", "grpc", "grpcs" ] = Field(default="http", description="Connection protocol.")
    user: Optional[str] = Field(default=None, description="Username for authentication.")
    password: Optional[str] = Field(default=None, description="Password for authentication.")
    database: Optional[str] = Field(default=None, description="Target database name.")
    timeout: str = Field(default="30s", description="Client operation timeout.")
    actions: List[MilvusVectorStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_endpoint_or_host(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("host")):
            raise ValueError("Either 'endpoint' or 'host' must be set, but not both")
        return values
