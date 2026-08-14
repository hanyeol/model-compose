from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import MilvusVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class MilvusVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.MILVUS]
    endpoint: Optional[str] = Field(default=None, description="Full Milvus endpoint URL. Mutually exclusive with `host`.")
    host: str = Field(default="localhost", description="Hostname or IP address of the Milvus server.")
    port: int = Field(default=19530, ge=1, le=65535, description="TCP port the Milvus server listens on.")
    protocol: Literal[ "http", "https", "grpc", "grpcs" ] = Field(default="http", description="Scheme used to connect to Milvus.")
    user: Optional[str] = Field(default=None, description="Username used to authenticate with Milvus.")
    password: Optional[str] = Field(default=None, description="Password used to authenticate with Milvus.")
    database: Optional[str] = Field(default=None, description="Target Milvus database name.")
    timeout: Union[str, int, float] = Field(default="30s", description="Maximum seconds to wait for a Milvus operation before failing.")
    actions: List[MilvusVectorStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_endpoint_or_host(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("host")):
            raise ValueError("Either 'endpoint' or 'host' must be set, but not both")
        return values
