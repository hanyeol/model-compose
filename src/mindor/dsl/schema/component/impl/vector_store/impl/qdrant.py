from typing import Literal, Optional, Dict, List, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import QdrantVectorStoreActionConfig
from mindor.dsl.utils.annotation import get_model_union_keys
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class QdrantVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.QDRANT]
    url: Optional[str] = Field(default=None, description="Qdrant server URL (e.g., http://localhost:6333).")
    host: str = Field(default="localhost", description="Qdrant server hostname or IP address.")
    port: int = Field(default=6333, ge=1, le=65535, description="Qdrant server port number.")
    grpc_port: int = Field(default=6334, ge=1, le=65535, description="Qdrant gRPC port number.")
    https: bool = Field(default=False, description="Use HTTPS for connections.")
    api_key: Optional[str] = Field(default=None, description="API key for authentication.")
    prefix: Optional[str] = Field(default=None, description="Prefix for collections.")
    timeout: float = Field(default=5.0, description="Client operation timeout in seconds.")
    prefer_grpc: bool = Field(default=False, description="Prefer gRPC over HTTP/REST API.")
    actions: List[QdrantVectorStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(get_model_union_keys(QdrantVectorStoreActionConfig)) - set(CommonVectorStoreComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
