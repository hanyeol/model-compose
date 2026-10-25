from typing import Literal
from pydantic import Field
from .common import CommonAgentMemoryBufferConfig, AgentMemoryBufferDriverType

class MemoryAgentMemoryBufferConfig(CommonAgentMemoryBufferConfig):
    driver: Literal[AgentMemoryBufferDriverType.MEMORY] = Field(default=AgentMemoryBufferDriverType.MEMORY, description="In-process buffer backend for agent memory.")
