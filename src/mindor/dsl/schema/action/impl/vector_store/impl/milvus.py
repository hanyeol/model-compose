from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import (
    CommonVectorInsertActionConfig, 
    CommonVectorUpdateActionConfig, 
    CommonVectorSearchActionConfig, 
    CommonVectorDeleteActionConfig
)

class MilvusVectorInsertActionConfig(CommonVectorInsertActionConfig):
    collection: str = Field(..., description="Collection that receives the inserted vectors.")
    partition: Optional[str] = Field(default=None, description="Partition within the collection that receives the inserted vectors.")

class MilvusVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    collection: str = Field(..., description="Collection containing the vectors to update.")
    partition: Optional[str] = Field(default=None, description="Partition within the collection containing the vectors to update.")

class MilvusVectorSearchActionConfig(CommonVectorSearchActionConfig):
    collection: str = Field(..., description="Collection searched for similar vectors.")
    partitions: Optional[List[str]] = Field(default=None, description="Partitions searched within the collection.")

class MilvusVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    collection: str = Field(..., description="Collection that vectors are deleted from.")
    partition: Optional[str] = Field(default=None, description="Partition within the collection that vectors are deleted from.")

MilvusVectorStoreActionConfig = Annotated[
    Union[ 
        MilvusVectorInsertActionConfig,
        MilvusVectorUpdateActionConfig,
        MilvusVectorSearchActionConfig,
        MilvusVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
