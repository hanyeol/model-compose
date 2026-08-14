from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from .common import CommonQueueSubscriberControllerAdapterConfig, QueueSubscriberDriver

class RedisQueueSubscriberControllerAdapterConfig(CommonQueueSubscriberControllerAdapterConfig):
    driver: Literal[QueueSubscriberDriver.REDIS]
    url: Optional[str] = Field(default=None, description="Full connection URL for the Redis server. Mutually exclusive with `host`.")
    host: str = Field(default="localhost", description="Hostname or IP address of the Redis server.")
    port: int = Field(default=6379, ge=1, le=65535, description="TCP port the Redis server listens on.")
    secure: bool = Field(default=False, description="Whether to connect over TLS/SSL (equivalent to the rediss:// scheme).")
    database: int = Field(default=0, ge=0, le=15, description="Redis logical database number to select on connect.")
    password: Optional[str] = Field(default=None, description="Password for authenticating with Redis; may also be embedded in `url`.")
    pop_timeout: Union[str, int, float] = Field(default="1s", description="Blocking pop timeout before retrying the queue read (e.g., '1s', '500ms').")

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
