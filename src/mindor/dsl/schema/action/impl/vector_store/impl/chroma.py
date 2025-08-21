from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonVectorInsertActionConfig, CommonVectorUpdateActionConfig, CommonVectorSearchActionConfig, CommonVectorRemoveActionConfig

class ChromaVectorInsertActionConfig(CommonVectorInsertActionConfig):
    collection: str = Field(..., description="Target collection for vector insertion.")
    document: Optional[Union[str, Union[str, List[str]]]] = Field(default=None, description="Document text or list of documents to associate with vectors.")

class ChromaVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    collection: str = Field(..., description="Target collection for vector update.")
    document: Optional[Union[str, Union[str, List[str]]]] = Field(default=None, description="Document text or list of documents to update with vectors.")

class ChromaVectorSearchActionConfig(CommonVectorSearchActionConfig):
    collection: str = Field(..., description="Collection to search vectors from.")

class ChromaVectorRemoveActionConfig(CommonVectorRemoveActionConfig):
    collection: str = Field(..., description="Collection to remove vectors from.")

ChromaVectorStoreActionConfig = Annotated[
    Union[ 
        ChromaVectorInsertActionConfig,
        ChromaVectorUpdateActionConfig,
        ChromaVectorSearchActionConfig,
        ChromaVectorRemoveActionConfig
    ],
    Field(discriminator="method")
]
