from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import (
    CommonVectorInsertActionConfig, 
    CommonVectorUpdateActionConfig, 
    CommonVectorSearchActionConfig, 
    CommonVectorDeleteActionConfig
)

class QdrantVectorInsertActionConfig(CommonVectorInsertActionConfig):
    collection: str = Field(..., description="Collection that receives the inserted vectors.")

class QdrantVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    collection: str = Field(..., description="Collection containing the vectors to update.")

class QdrantVectorSearchActionConfig(CommonVectorSearchActionConfig):
    collection: str = Field(..., description="Collection searched for similar vectors.")

class QdrantVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    collection: str = Field(..., description="Collection that vectors are deleted from.")

QdrantVectorStoreActionConfig = Annotated[
    Union[ 
        QdrantVectorInsertActionConfig,
        QdrantVectorUpdateActionConfig,
        QdrantVectorSearchActionConfig,
        QdrantVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
