from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonVectorInsertActionConfig, CommonVectorUpdateActionConfig, CommonVectorSearchActionConfig, CommonVectorDeleteActionConfig

class FaissVectorInsertActionConfig(CommonVectorInsertActionConfig):
    pass

class FaissVectorUpdateActionConfig(CommonVectorUpdateActionConfig):
    pass

class FaissVectorSearchActionConfig(CommonVectorSearchActionConfig):
    pass

class FaissVectorDeleteActionConfig(CommonVectorDeleteActionConfig):
    pass

FaissVectorStoreActionConfig = Annotated[
    Union[ 
        FaissVectorInsertActionConfig,
        FaissVectorUpdateActionConfig,
        FaissVectorSearchActionConfig,
        FaissVectorDeleteActionConfig
    ],
    Field(discriminator="method")
]
