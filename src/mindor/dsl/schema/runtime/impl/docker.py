from typing import Union, Literal, Optional
from pydantic import Field, model_validator
from mindor.dsl.schema.containers.docker import DockerContainerConfig
from mindor.dsl.schema.runtime.remote import RemoteTransportConfig
from .common import RuntimeType, CommonRuntimeConfig

class DockerRuntimeConfig(CommonRuntimeConfig, DockerContainerConfig):
    type: Literal[RuntimeType.DOCKER]
    remote: Optional[RemoteTransportConfig] = Field(default=None, description="Remote host configuration; when set, the container runs on that host's docker daemon reached over the chosen transport.")
    start_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the container worker to connect and report ready.")
    stop_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the container to stop gracefully before being killed.")

    @model_validator(mode="after")
    def reject_unsupported_remote(self):
        if self.remote is not None:
            raise ValueError("`docker` runtime does not support `remote:` yet.")
        return self
