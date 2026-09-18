from typing import Literal
from pydantic import Field
from .common import CommonModelMemoryBufferConfig, ModelMemoryBufferDriverType

class MemoryModelMemoryBufferConfig(CommonModelMemoryBufferConfig):
    driver: Literal[ModelMemoryBufferDriverType.MEMORY] = Field(default=ModelMemoryBufferDriverType.MEMORY, description="In-process buffer backend for model memory.")
