from typing import List
from pathlib import Path
from mindor.dsl.schema.containers.apple_container import AppleContainerPortConfig
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.runtime.common import ContainerImageKind
from mindor.core.runtime.apple_container import AppleContainerRuntimeBackend, AppleContainerRuntimeParams
from .common import ControllerContainerRuntimeManager, ControllerContainerSpec

class ControllerAppleContainerRuntimeBackend(AppleContainerRuntimeBackend):
    """Apple Container backend for a controller runtime."""

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

    def _resolve_runtime_params(self) -> AppleContainerRuntimeParams:
        params = super()._resolve_runtime_params()

        if params.ports is None:
            params.ports = [
                AppleContainerPortConfig(container_port=port, host_port=port, host_ip=host_ip)
                for host_ip, port in ControllerContainerSpec.resolve_service_ports(self.config)
            ]

        return params

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

class ControllerAppleContainerRuntimeManager(ControllerContainerRuntimeManager):
    """Facade — composes the Apple Container backend with the controller lifecycle."""
    def _create_backend(
        self,
        config: ControllerConfig,
        image_kind: ContainerImageKind,
        verbose: bool,
    ) -> ControllerAppleContainerRuntimeBackend:
        return ControllerAppleContainerRuntimeBackend(config, image_kind, verbose)
