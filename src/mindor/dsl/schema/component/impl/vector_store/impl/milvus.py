from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import MilvusVectorStoreActionConfig
from mindor.dsl.utils.annotation import get_model_union_keys
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class MilvusVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.MILVUS]
    endpoint: Optional[str] = Field(default=None, description="Milvus server endpoint URL.")
    host: str = Field(default="localhost", description="Milvus server hostname or IP address.")
    port: int = Field(default=19530, description="Milvus server port number.")
    protocol: Literal[ "http", "https", "grpc", "grpcs" ] = Field(default="http", description="Connection protocol.")
    user: Optional[str] = Field(default=None, description="Username for authentication.")
    password: Optional[str] = Field(default=None, description="Password for authentication.")
    database: Optional[str] = Field(default=None, description="Target database name.")
    timeout: float = Field(default=30.0, description="Client operation timeout in seconds.")
    actions: List[MilvusVectorStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_endpoint_or_host(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("host")):
            raise ValueError("Either 'endpoint' or 'host' must be set, but not both.")
        return values

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(get_model_union_keys(MilvusVectorStoreActionConfig)) - set(CommonVectorStoreComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
