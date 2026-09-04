from typing import Union, Literal
from pydantic import Field
from mindor.dsl.schema.containers.apple_container import AppleContainerConfig
from .common import RuntimeType, CommonRuntimeConfig

class AppleContainerRuntimeConfig(CommonRuntimeConfig, AppleContainerConfig):
    type: Literal[RuntimeType.APPLE_CONTAINER]
    start_timeout: Union[str, int, float] = Field(default="90s", description="Maximum time to wait for the container worker to connect and report ready.")
    stop_timeout: Union[str, int, float] = Field(default="30s", description="Maximum time to wait for the container to stop gracefully before being killed.")
