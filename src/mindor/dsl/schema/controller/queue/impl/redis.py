from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from .common import CommonControllerQueueConfig, ControllerQueueDriver

class RedisControllerQueueConfig(CommonControllerQueueConfig):
    driver: Literal[ControllerQueueDriver.REDIS]
    url: Optional[str] = Field(default=None, description="Redis connection URL (e.g., redis://localhost:6379, rediss://localhost:6379 for TLS).")
    host: str = Field(default="localhost", description="Redis server hostname or IP address.")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis server port number.")
    secure: bool = Field(default=False, description="Use TLS/SSL for connections (equivalent to rediss:// protocol).")
    database: int = Field(default=0, ge=0, le=15, description="Redis database number.")
    password: Optional[str] = Field(default=None, description="Redis password. Can also be specified in the URL.")

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
