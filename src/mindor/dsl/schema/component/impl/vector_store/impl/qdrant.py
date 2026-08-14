from typing import Union, Literal, Optional, Dict, List, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import QdrantVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class QdrantVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.QDRANT]
    url: Optional[str] = Field(default=None, description="Full Qdrant URL (e.g., http://host:port). Mutually exclusive with `host`.")
    host: str = Field(default="localhost", description="Hostname or IP address of the Qdrant server.")
    port: int = Field(default=6333, ge=1, le=65535, description="TCP port the Qdrant REST API listens on.")
    grpc_port: int = Field(default=6334, ge=1, le=65535, description="TCP port the Qdrant gRPC API listens on.")
    https: bool = Field(default=False, description="Whether to connect to Qdrant over HTTPS.")
    api_key: Optional[str] = Field(default=None, description="API key used to authenticate with Qdrant.")
    prefix: Optional[str] = Field(default=None, description="Prefix prepended to Qdrant collection names.")
    timeout: Union[str, int, float] = Field(default="30s", description="Maximum seconds to wait for a Qdrant operation before failing.")
    prefer_grpc: bool = Field(default=False, description="Whether to prefer the gRPC API over REST when both are available.")
    actions: List[QdrantVectorStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
