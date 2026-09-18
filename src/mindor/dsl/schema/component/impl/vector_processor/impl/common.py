from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class VectorProcessorDriverType(str, Enum):
    NATIVE = "native"

class CommonVectorProcessorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VECTOR_PROCESSOR]
    driver: VectorProcessorDriverType = Field(..., description="Backend implementation used for vector processing.")
