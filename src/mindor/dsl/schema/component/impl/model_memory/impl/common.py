from enum import Enum
from pydantic import BaseModel

class ModelMemoryStorageDriverType(str, Enum):
    SQLITE = "sqlite"
    REDIS  = "redis"

class CommonModelMemoryStorageConfig(BaseModel):
    driver: ModelMemoryStorageDriverType

class ModelMemoryBufferDriverType(str, Enum):
    MEMORY = "memory"
    REDIS  = "redis"

class CommonModelMemoryBufferConfig(BaseModel):
    driver: ModelMemoryBufferDriverType
