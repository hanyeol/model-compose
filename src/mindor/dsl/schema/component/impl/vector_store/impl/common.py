from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType
from .types import VectorStoreDriver

class CommonVectorStoreComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VECTOR_STORE]
    driver: VectorStoreDriver = Field(..., description="Vector store backend driver.")
