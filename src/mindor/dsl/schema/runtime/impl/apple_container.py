from typing import Union, Literal, Optional
from pydantic import Field
from mindor.dsl.schema.containers.apple_container import AppleContainerConfig
from mindor.dsl.schema.runtime.remote import RemoteTransportConfig
from .common import RuntimeType, CommonRuntimeConfig

class AppleContainerRuntimeConfig(CommonRuntimeConfig, AppleContainerConfig):
    type: Literal[RuntimeType.APPLE_CONTAINER]
    remote: Optional[RemoteTransportConfig] = Field(default=None, description="Remote host configuration; when set, the container runs on that host's container subsystem reached over the chosen transport.")
    start_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the container worker to connect and report ready.")
    stop_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the container to stop gracefully before being killed.")
