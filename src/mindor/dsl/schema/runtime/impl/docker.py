from typing import Union, Literal
from pydantic import Field
from mindor.dsl.schema.containers.docker import DockerContainerConfig
from .common import RuntimeType, CommonRuntimeConfig

class DockerRuntimeConfig(CommonRuntimeConfig, DockerContainerConfig):
    type: Literal[RuntimeType.DOCKER]

    start_timeout: Union[str, int, float] = Field(default="90s", description="Worker connect / STATUS(ready) timeout.")
    stop_timeout: Union[str, int, float] = Field(default="30s", description="Container graceful stop timeout.")
