from typing import Literal
from pydantic import Field
from mindor.dsl.schema.containers.docker import DockerContainerConfig
from .common import CommonSystemConfig
from .types import SystemType

class DockerSystemConfig(CommonSystemConfig, DockerContainerConfig):
    type: Literal[SystemType.DOCKER] = Field(default=SystemType.DOCKER, description="Docker system type.")
