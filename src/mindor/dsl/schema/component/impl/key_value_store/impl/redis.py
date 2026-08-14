from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import RedisKeyValueStoreActionConfig
from .common import CommonKeyValueStoreComponentConfig, KeyValueStoreDriver

class RedisKeyValueStoreComponentConfig(CommonKeyValueStoreComponentConfig):
    driver: Literal[KeyValueStoreDriver.REDIS]
    url: Optional[str] = Field(default=None, description="Full Redis connection URL (e.g., redis://host:port). Mutually exclusive with `host`.")
    host: str = Field(default="localhost", description="Hostname or IP address of the Redis server.")
    port: int = Field(default=6379, ge=1, le=65535, description="TCP port the Redis server listens on.")
    secure: bool = Field(default=False, description="Whether to connect over TLS (equivalent to the rediss:// scheme).")
    database: int = Field(default=0, ge=0, le=15, description="Redis logical database index to select on connect.")
    password: Optional[str] = Field(default=None, description="Password used to authenticate with Redis; may also be embedded in `url`.")
    actions: List[RedisKeyValueStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both")
        return values
