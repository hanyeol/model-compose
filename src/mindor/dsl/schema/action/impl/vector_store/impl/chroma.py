from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import (
    CommonVectorInsertActionConfig, 
    CommonVectorUpdateActionConfig, 
    CommonVectorSearchActionConfig, 
    CommonVectorDeleteActionConfig
)

class ChromaVectorInsertActionConfig(CommonVectorInsertActionConfig):
    collection: str = Field(..., description="Collection that receives the inserted vectors.")
    document: Optional[Union[str, Union[str, List[str]]]] = Field(default=None, description="Document text associated with each inserted vector.")

class ChromaVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    collection: str = Field(..., description="Collection containing the vectors to update.")
    document: Optional[Union[str, Union[str, List[str]]]] = Field(default=None, description="Document text written alongside the updated vectors.")

class ChromaVectorSearchActionConfig(CommonVectorSearchActionConfig):
    collection: str = Field(..., description="Collection searched for similar vectors.")

class ChromaVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    collection: str = Field(..., description="Collection that vectors are deleted from.")

ChromaVectorStoreActionConfig = Annotated[
    Union[ 
        ChromaVectorInsertActionConfig,
        ChromaVectorUpdateActionConfig,
        ChromaVectorSearchActionConfig,
        ChromaVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
