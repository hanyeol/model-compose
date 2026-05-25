from typing import Literal, Optional
from pydantic import Field
from .common import CommonModelMemoryBufferConfig, ModelMemoryBufferDriver

class RedisModelMemoryBufferConfig(CommonModelMemoryBufferConfig):
    driver: Literal[ModelMemoryBufferDriver.REDIS] = Field(description="Redis buffer driver.")
    url: Optional[str] = Field(default=None, description="Redis connection URL (e.g., redis://localhost:6379).")
    host: str = Field(default="localhost", description="Redis server hostname.")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis server port.")
    secure: bool = Field(default=False, description="Use TLS/SSL for connections.")
    password: Optional[str] = Field(default=None, description="Redis password.")
    database: int = Field(default=0, ge=0, description="Redis database number.")
    prefix: str = Field(default="model-memory:", description="Key prefix for Redis keys.")
