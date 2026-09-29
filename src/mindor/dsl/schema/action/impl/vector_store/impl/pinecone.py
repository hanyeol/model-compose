from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonVectorInsertActionConfig, 
    CommonVectorUpdateActionConfig, 
    CommonVectorSearchActionConfig, 
    CommonVectorDeleteActionConfig
)

class PineconeVectorInsertActionConfig(CommonVectorInsertActionConfig):
    index_name: Optional[str] = Field(default=None, description="Pinecone index name. Overrides component level index_name.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace.")

class PineconeVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    index_name: Optional[str] = Field(default=None, description="Pinecone index name. Overrides component level index_name.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace.")

class PineconeVectorSearchActionConfig(CommonVectorSearchActionConfig):
    index_name: Optional[str] = Field(default=None, description="Pinecone index name. Overrides component level index_name.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace.")

class PineconeVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    index_name: Optional[str] = Field(default=None, description="Pinecone index name. Overrides component level index_name.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace.")

PineconeVectorStoreActionConfig = Annotated[
    Union[ 
        PineconeVectorInsertActionConfig,
        PineconeVectorUpdateActionConfig,
        PineconeVectorSearchActionConfig,
        PineconeVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
