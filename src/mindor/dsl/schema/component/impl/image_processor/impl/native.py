from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ImageProcessorActionConfig
from .common import CommonImageProcessorComponentConfig, ImageProcessorDriverType

class NativeImageProcessorComponentConfig(CommonImageProcessorComponentConfig):
    driver: Literal[ImageProcessorDriverType.NATIVE]
    actions: List[ImageProcessorActionConfig] = Field(default_factory=list)
