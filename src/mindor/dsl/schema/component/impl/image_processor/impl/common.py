from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class ImageProcessorDriver(str, Enum):
    NATIVE = "native"

class CommonImageProcessorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.IMAGE_PROCESSOR]
    driver: ImageProcessorDriver = Field(..., description="Image processing backend driver.")
