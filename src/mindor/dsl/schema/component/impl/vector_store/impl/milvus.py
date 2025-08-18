from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import MilvusVectorStoreActionConfig
from mindor.dsl.utils.annotation import get_model_union_keys
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class MilvusVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.MILVUS]
    endpoint: Optional[str] = Field(default=None, description="")
    host: str = Field(default="localhost", description="Milvus server hostname or IP address.")
    port: int = Field(default=19530, description="Milvus server port number.")
    protocol: Literal[ "grpc", "grpcs", "http", "https" ] = Field(default="grpc", description="")
    user: Optional[str] = Field(default=None, description="Milvus username." )
    password: Optional[str] = Field(default=None, description="Milvus password.")
    database_name: Optional[str] = Field(default=None, description="Milvus database name.")
    timeout: float = Field(default=30.0, description="Timeout in seconds for Milvus client operations.")
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
