from typing import Union, Literal, Optional
from pydantic import Field
from mindor.dsl.schema.containers.docker import DockerContainerConfig
from .common import RuntimeType, CommonRuntimeConfig

class DockerRuntimeConfig(CommonRuntimeConfig, DockerContainerConfig):
    type: Literal[RuntimeType.DOCKER]
    start_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the container worker to connect and report ready.")
    stop_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the container to stop gracefully before being killed.")
