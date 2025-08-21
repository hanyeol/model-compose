from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonVectorInsertActionConfig, CommonVectorUpdateActionConfig, CommonVectorSearchActionConfig, CommonVectorDeleteActionConfig

class QdrantVectorInsertActionConfig(CommonVectorInsertActionConfig):
    collection: str = Field(..., description="Target collection for vector insertion.")

class QdrantVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    collection: str = Field(..., description="Target collection for vector update.")

class QdrantVectorSearchActionConfig(CommonVectorSearchActionConfig):
    collection: str = Field(..., description="Collection to search vectors from.")

class QdrantVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    collection: str = Field(..., description="Collection to remove vectors from.")

QdrantVectorStoreActionConfig = Annotated[
    Union[ 
        QdrantVectorInsertActionConfig,
        QdrantVectorUpdateActionConfig,
        QdrantVectorSearchActionConfig,
        QdrantVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
