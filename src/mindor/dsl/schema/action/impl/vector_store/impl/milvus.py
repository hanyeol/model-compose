from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonVectorInsertActionConfig, CommonVectorUpdateActionConfig, CommonVectorSearchActionConfig, CommonVectorRemoveActionConfig

class MilvusVectorInsertActionConfig(CommonVectorInsertActionConfig):
    partition_name: Optional[str] = Field(default=None, description="Name of the partition where vectors will be inserted.")

class MilvusVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    partition_name: Optional[str] = Field(default=None, description="Name of the partition where vectors will be updated.")

class MilvusVectorSearchActionConfig(CommonVectorSearchActionConfig):
    partition_name: Optional[str] = Field(default=None, description="Name of the partition to search vectors from.")

class MilvusVectorRemoveActionConfig(CommonVectorRemoveActionConfig):
    partition_name: Optional[str] = Field(default=None, description="Name of the partition from which vectors will be removed.")

MilvusVectorStoreActionConfig = Annotated[
    Union[ 
        MilvusVectorInsertActionConfig,
        MilvusVectorUpdateActionConfig,
        MilvusVectorSearchActionConfig,
        MilvusVectorRemoveActionConfig
    ],
    Field(discriminator="method")
]
