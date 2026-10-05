from typing import Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.action import PineconeVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriverType

class PineconeVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriverType.PINECONE]
    api_key: Optional[str] = Field(default=None, description="Pinecone API key for authentication.")
    environment: Optional[str] = Field(default=None, description="Pinecone environment (e.g., us-west1-gcp, gcp-starter).")
    pool_threads: int = Field(default=1, ge=1, description="Number of threads for connection pooling.")
    actions: List[PineconeVectorStoreActionConfig] = Field(default_factory=list)
