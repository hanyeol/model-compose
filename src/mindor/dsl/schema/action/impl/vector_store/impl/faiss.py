from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonVectorInsertActionConfig, CommonVectorUpdateActionConfig, CommonVectorSearchActionConfig, CommonVectorRemoveActionConfig

class FaissVectorInsertActionConfig(CommonVectorInsertActionConfig):
    pass

class FaissVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    pass

class FaissVectorSearchActionConfig(CommonVectorSearchActionConfig):
    pass

class FaissVectorRemoveActionConfig(CommonVectorRemoveActionConfig):
    pass

FaissVectorStoreActionConfig = Annotated[
    Union[ 
        FaissVectorInsertActionConfig,
        FaissVectorUpdateActionConfig,
        FaissVectorSearchActionConfig,
        FaissVectorRemoveActionConfig
    ],
    Field(discriminator="method")
]
