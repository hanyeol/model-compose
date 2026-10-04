from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonVectorInsertActionConfig,
    CommonVectorUpdateActionConfig,
    CommonVectorSearchActionConfig,
    CommonVectorDeleteActionConfig
)

class PineconeVectorInsertActionConfig(CommonVectorInsertActionConfig):
    collection: str = Field(..., description="Pinecone index that receives the inserted vectors.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace. Overrides component-level namespace.")

class PineconeVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    collection: str = Field(..., description="Pinecone index containing the vectors to update.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace. Overrides component-level namespace.")

class PineconeVectorSearchActionConfig(CommonVectorSearchActionConfig):
    collection: str = Field(..., description="Pinecone index searched for similar vectors.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace. Overrides component-level namespace.")

class PineconeVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    collection: str = Field(..., description="Pinecone index that vectors are deleted from.")
    namespace: Optional[str] = Field(default=None, description="Pinecone namespace. Overrides component-level namespace.")

PineconeVectorStoreActionConfig = Annotated[
    Union[
        PineconeVectorInsertActionConfig,
        PineconeVectorUpdateActionConfig,
        PineconeVectorSearchActionConfig,
        PineconeVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
