from typing import Literal, Optional
from pydantic import Field
from .common import CommonModelMemoryStorageConfig, ModelMemoryStorageDriver

class RedisModelMemoryStorageConfig(CommonModelMemoryStorageConfig):
    driver: Literal[ModelMemoryStorageDriver.REDIS] = Field(description="Redis storage driver.")
    url: Optional[str] = Field(default=None, description="Redis connection URL.")
    host: str = Field(default="localhost", description="Redis server hostname or IP address.")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis server port number.")
    secure: bool = Field(default=False, description="Use TLS/SSL for connections (equivalent to rediss:// protocol).")
    password: Optional[str] = Field(default=None, description="Redis password.")
    database: int = Field(default=0, ge=0, description="Redis database number.")
