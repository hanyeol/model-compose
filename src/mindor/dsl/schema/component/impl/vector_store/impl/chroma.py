from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import ChromaVectorStoreActionConfig
from mindor.dsl.utils.annotation import get_model_union_keys
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class ChromaVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.CHROMA]
    mode: Literal[ "local", "server" ] = Field(default="local", description="Run Chroma locally or connect to a server.")
    storage_dir: str = Field(default="./chroma", description="Local storage path.")
    host: str = Field(default="localhost", description="Chroma server hostname or IP address.")
    port: int = Field(default=8000, description="Chroma server port number.")
    protocol: Literal[ "http", "https" ] = Field(default="http", description="Connection protocol.")
    tenant: Optional[str] = Field(default=None, description="Target tenant name.")
    database: Optional[str] = Field(default=None, description="Target database name.")
    timeout: float = Field(default=30.0, description="Client operation timeout in seconds.")
    actions: List[ChromaVectorStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(get_model_union_keys(ChromaVectorStoreActionConfig)) - set(CommonVectorStoreComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
