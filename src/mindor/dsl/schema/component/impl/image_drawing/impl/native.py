from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ImageDrawingActionConfig
from .common import CommonImageDrawingComponentConfig, ImageDrawingDriver

class NativeImageDrawingComponentConfig(CommonImageDrawingComponentConfig):
    driver: Literal[ImageDrawingDriver.NATIVE]
    actions: List[ImageDrawingActionConfig] = Field(default_factory=list)
