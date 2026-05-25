from typing import Literal
from pydantic import Field
from .common import CommonModelMemoryBufferConfig, ModelMemoryBufferDriver

class MemoryModelMemoryBufferConfig(CommonModelMemoryBufferConfig):
    driver: Literal[ModelMemoryBufferDriver.MEMORY] = Field(default=ModelMemoryBufferDriver.MEMORY, description="In-memory buffer driver.")
