from typing import List
from pathlib import Path
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.core.runtime.common import ContainerImageKind
from mindor.core.runtime.docker import DockerRuntimeBackend, DockerRuntimeParams
from .common import ControllerContainerRuntimeLauncher, ControllerImageSpec

class ControllerDockerBackend(DockerRuntimeBackend):
    """Docker backend for a controller runtime."""

    def __init__(self, config: ControllerConfig, image_kind: ContainerImageKind, verbose: bool):
        self.config: ControllerConfig = config

        super().__init__(image_kind=image_kind, verbose=verbose)

    def _default_image_tag(self) -> str:
        if self.config.runtime.build:
            return f"mindor/controller-{ControllerImageSpec.project_name(self.config)}:latest"
        if self._image_kind == ContainerImageKind.DERIVED:
            return self._derived_image_tag()
        return self._standard_image_tag()

    def _default_container_name(self) -> str:
        return self.config.name or f"mindor-controller-{ControllerImageSpec.project_name(self.config)}"

    def _resolve_runtime_params(self, config: DockerRuntimeConfig) -> DockerRuntimeParams:
        params = super()._resolve_runtime_params(config)

        if not params.working_dir:
            params.working_dir = "/workspace"

        if params.ports is None:
            webui_port = getattr(self.config.webui, "port", None)
            params.ports = list(set(ControllerImageSpec.resolve_adapter_ports(self.config) + ([ webui_port ] if webui_port else [])))

        if not params.extra_hosts:
            params.extra_hosts = {}

        params.extra_hosts.setdefault("host.docker.internal", "host-gateway")

        return params

    def _image_assets_dir(self) -> Path:
        return ControllerImageSpec.assets_dir()

    def _standard_image_tag(self) -> str:
        return ControllerImageSpec.standard_tag()

    def _derived_image_tag(self) -> str:
        return ControllerImageSpec.derived_tag(self.config)

    def _standard_image_command(self) -> List[str]:
        return ControllerImageSpec.standard_command()

class ControllerDockerRuntimeLauncher(ControllerContainerRuntimeLauncher):
    """Facade — composes the Docker backend with the controller lifecycle."""
    def __init__(self, config: ControllerConfig, verbose: bool):
        image_kind = ControllerImageSpec.resolve_image_kind(config)
        backend = ControllerDockerBackend(config, image_kind, verbose)
        super().__init__(config=config, backend=backend, image_kind=image_kind)
