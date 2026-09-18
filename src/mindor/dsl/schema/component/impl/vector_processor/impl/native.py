from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import VectorProcessorActionConfig
from .common import CommonVectorProcessorComponentConfig, VectorProcessorDriverType

class NativeVectorProcessorComponentConfig(CommonVectorProcessorComponentConfig):
    driver: Literal[VectorProcessorDriverType.NATIVE]
    actions: List[VectorProcessorActionConfig] = Field(default_factory=list)
