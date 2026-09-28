from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import FaissVectorStoreActionConfig
from .common import CommonVectorStoreComponentConfig, VectorStoreDriverType

class FaissVectorStoreComponentConfig(CommonVectorStoreComponentConfig):
    driver: Literal[VectorStoreDriverType.FAISS]
    dimension: int = Field(..., gt=0, description="Dimensionality of the vectors stored in this index.")
    metric: Literal[ "l2", "ip", "cosine" ] = Field(default="l2", description="Distance metric used for similarity search.")
    storage_dir: Optional[str] = Field(default=None, description="Directory to persist the index and metadata to disk.")
    actions: List[FaissVectorStoreActionConfig] = Field(default_factory=list)
