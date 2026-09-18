from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class ImageProcessorDriverType(str, Enum):
    NATIVE = "native"

class CommonImageProcessorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.IMAGE_PROCESSOR]
    driver: ImageProcessorDriverType = Field(..., description="Backend implementation used for image processing.")
