from typing import Literal, Optional
from pydantic import Field
from .common import CommonModelMemoryBufferConfig, ModelMemoryBufferDriver

class RedisModelMemoryBufferConfig(CommonModelMemoryBufferConfig):
    driver: Literal[ModelMemoryBufferDriver.REDIS] = Field(description="Redis buffer backend for short-term model memory.")
    url: Optional[str] = Field(default=None, description="Full Redis connection URL (e.g., redis://host:6379 or rediss://host:6380).")
    host: str = Field(default="localhost", description="Hostname or IP address of the Redis server.")
    port: int = Field(default=6379, ge=1, le=65535, description="TCP port the Redis server listens on.")
    secure: bool = Field(default=False, description="Whether to connect over TLS.")
    password: Optional[str] = Field(default=None, description="Password used to authenticate with the Redis server.")
    database: int = Field(default=0, ge=0, description="Redis logical database index to select after connecting.")
    prefix: str = Field(default="model-memory:", description="Prefix prepended to every Redis key written by the buffer.")
