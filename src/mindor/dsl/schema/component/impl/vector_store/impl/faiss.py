from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import FaissVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriverType

class FaissVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriverType.FAISS]
    actions: List[FaissVectorStoreActionConfig] = Field(default_factory=list)
