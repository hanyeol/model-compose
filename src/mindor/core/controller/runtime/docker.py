from typing import List
from pathlib import Path
from mindor.dsl.schema.containers.docker import DockerPortConfig
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.runtime.common import ContainerImageKind
from mindor.core.foundation.containers.docker import DockerContainerOptions
from mindor.core.runtime.docker import DockerRuntimeBackend
from .common import ControllerContainerRuntimeManager, ControllerContainerSpec

class ControllerDockerRuntimeBackend(DockerRuntimeBackend):
    """Docker backend for a controller runtime."""
    def __init__(self, config: ControllerConfig, image_kind: ContainerImageKind, verbose: bool):
        super().__init__(runtime_config=config.runtime, image_kind=image_kind, verbose=verbose)

        self.config: ControllerConfig = config

    def _default_image_tag(self) -> str:
        if self._image_kind == ContainerImageKind.CUSTOM:
            return self._custom_image_tag()
        if self._image_kind == ContainerImageKind.DERIVED:
            return self._derived_image_tag()
        return self._standard_image_tag()

    def _default_container_name(self) -> str:
        return ControllerContainerSpec.default_container_name(self.config.name)

    def _resolve_container_options(self) -> DockerContainerOptions:
        options = super()._resolve_container_options()

        if not self.config.runtime.working_dir:
            options.working_dir = "/workspace"

        if self.config.runtime.ports is None:
            options.ports = []
            for host_ip, port in ControllerContainerSpec.resolve_service_ports(self.config):
                options.ports.append(DockerPortConfig(container_port=port, host_port=port, host_ip=host_ip))

        return options

    def _image_assets_dir(self) -> Path:
        return ControllerContainerSpec.image_assets_dir()

    def _standard_image_tag(self) -> str:
        return ControllerContainerSpec.standard_image_tag()

    def _derived_image_tag(self) -> str:
        return ControllerContainerSpec.derived_image_tag(self.config.name)

    def _custom_image_tag(self) -> str:
        return ControllerContainerSpec.custom_image_tag(self.config.name)

    def _standard_image_command(self) -> List[str]:
        return ControllerContainerSpec.standard_image_command()

class ControllerDockerRuntimeManager(ControllerContainerRuntimeManager):
    """Facade — composes the Docker backend with the controller lifecycle."""
    def _create_backend(
        self,
        config: ControllerConfig,
        image_kind: ContainerImageKind,
        verbose: bool,
    ) -> ControllerDockerRuntimeBackend:
        return ControllerDockerRuntimeBackend(config, image_kind, verbose)
