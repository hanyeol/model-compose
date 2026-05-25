from enum import Enum
from pydantic import BaseModel

class ModelMemoryStorageDriver(str, Enum):
    SQLITE = "sqlite"
    REDIS  = "redis"

class CommonModelMemoryStorageConfig(BaseModel):
    driver: ModelMemoryStorageDriver

class ModelMemoryBufferDriver(str, Enum):
    MEMORY = "memory"
    REDIS  = "redis"

class CommonModelMemoryBufferConfig(BaseModel):
    driver: ModelMemoryBufferDriver
