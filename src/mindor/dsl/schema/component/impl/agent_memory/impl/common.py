from enum import Enum
from pydantic import BaseModel

class AgentMemoryStorageDriverType(str, Enum):
    SQLITE = "sqlite"
    REDIS  = "redis"

class CommonAgentMemoryStorageConfig(BaseModel):
    driver: AgentMemoryStorageDriverType

class AgentMemoryBufferDriverType(str, Enum):
    MEMORY = "memory"
    REDIS  = "redis"

class CommonAgentMemoryBufferConfig(BaseModel):
    driver: AgentMemoryBufferDriverType
