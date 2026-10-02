from typing import Union, Literal, Optional, Dict, List, Any
from pydantic import Field
from mindor.dsl.schema.action import PineconeVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriverType

class PineconeVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriverType.PINECONE]
    api_key: Optional[str] = Field(default=None, description="Pinecone API key for authentication.")
    environment: Optional[str] = Field(default=None, description="Pinecone environment (e.g., us-west1-gcp, gcp-starter).")
    index_name: Optional[str] = Field(default=None, description="Pinecone index name.")
    namespace: Optional[str] = Field(default=None, description="Default namespace for vector operations.")
    dimension: Optional[int] = Field(default=None, gt=0, description="Vector dimension.")
    metric: Optional[Literal["cosine", "euclidean", "dotproduct"]] = Field(default="cosine", description="Distance metric used for similarity search.")
    pool_threads: int = Field(default=1, ge=1, description="Number of threads for connection pooling.")
    actions: List[PineconeVectorStoreActionConfig] = Field(default_factory=list)
