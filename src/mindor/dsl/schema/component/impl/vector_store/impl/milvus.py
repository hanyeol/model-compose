from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import MilvusVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriver

class MilvusVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriver.MILVUS]
    host: str = Field(default="localhost", description="Milvus server hostname or IP address.")
    port: int = Field(default=19530, description="Milvus server port number.")
    user: Optional[str] = Field(default=None, description="Milvus username." )
    password: Optional[str] = Field(default=None, description="Milvus password.")
    collection_name: str = Field(..., description="Name of the Milvus collection to store vectors.")
    database_name: Optional[str] = Field(default=None, description="Milvus database name.")
    use_tls: bool = Field(default=False, description="Whether to use TLS for the Milvus connection.")
    timeout: float = Field(default=30.0, description="Timeout in seconds for Milvus client operations.")
    actions: List[MilvusVectorStoreActionConfig] = Field(default_factory=list)
