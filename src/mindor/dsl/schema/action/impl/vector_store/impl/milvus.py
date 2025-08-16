from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonVectorInsertActionConfig, CommonVectorUpdateActionConfig, CommonVectorSearchActionConfig, CommonVectorRemoveActionConfig

class MilvusVectorInsertActionConfig(CommonVectorInsertActionConfig):
    pass

class MilvusVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    pass

class MilvusVectorSearchActionConfig(CommonVectorSearchActionConfig):
    pass

class MilvusVectorRemoveActionConfig(CommonVectorRemoveActionConfig):
    pass

MilvusVectorStoreActionConfig = Annotated[
    Union[ 
        MilvusVectorInsertActionConfig,
        MilvusVectorUpdateActionConfig,
        MilvusVectorSearchActionConfig,
        MilvusVectorRemoveActionConfig
    ],
    Field(discriminator="type")
]
