from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ImageProcessorActionConfig
from .common import CommonImageProcessorComponentConfig, ImageProcessorDriver

class NativeImageProcessorComponentConfig(CommonImageProcessorComponentConfig):
    driver: Literal[ImageProcessorDriver.NATIVE]
    actions: List[ImageProcessorActionConfig] = Field(default_factory=list)
