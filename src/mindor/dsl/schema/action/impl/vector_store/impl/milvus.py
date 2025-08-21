from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonVectorInsertActionConfig, CommonVectorUpdateActionConfig, CommonVectorSearchActionConfig, CommonVectorDeleteActionConfig

class MilvusVectorInsertActionConfig(CommonVectorInsertActionConfig):
    collection: str = Field(..., description="Target collection for vector insertion.")
    partition: Optional[str] = Field(default=None, description="Partition to insert vectors into.")

class MilvusVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    collection: str = Field(..., description="Target collection for vector update.")
    partition: Optional[str] = Field(default=None, description="Partition to update vectors in.")

class MilvusVectorSearchActionConfig(CommonVectorSearchActionConfig):
    collection: str = Field(..., description="Collection to search vectors from.")
    partitions: Optional[List[str]] = Field(default=None, description="Partitions to search within.")

class MilvusVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    collection: str = Field(..., description="Collection to remove vectors from.")
    partition: Optional[str] = Field(default=None, description="Partition to remove vectors from.")

MilvusVectorStoreActionConfig = Annotated[
    Union[ 
        MilvusVectorInsertActionConfig,
        MilvusVectorUpdateActionConfig,
        MilvusVectorSearchActionConfig,
        MilvusVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
