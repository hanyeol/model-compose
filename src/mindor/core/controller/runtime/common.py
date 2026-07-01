from typing import List
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.controller.adapter.impl.types import ControllerAdapterType
from mindor.core.runtime.common import ContainerImageKind, ContainerRuntimeBackend
from mindor.core.logger import logging
from mindor.version import __version__
from .base.specs import ControllerRuntimeSpecs
from .base.workspace import generate_workspace_bundle
from pathlib import Path
import re

class ControllerImageSpec:
    """Controller-image conventions shared by Docker/Apple backends."""

    @staticmethod
    def standard_tag() -> str:
        return f"mindor/controller:{__version__}"

    @staticmethod
    def derived_tag(config: ControllerConfig) -> str:
        return f"mindor/controller-{ControllerImageSpec.project_name(config)}:{__version__}"

    @staticmethod
    def standard_command() -> List[str]:
        return [ "python", "-m", "mindor.cli.compose", "up" ]

    @staticmethod
    def assets_dir() -> Path:
        return Path(__file__).resolve().parent / "container" / "assets"

    @staticmethod
    def project_name(config: ControllerConfig) -> str:
        # Follows docker-compose: compose `name:` wins, else sanitized cwd basename.
        # Sanitization rule: lowercased, only [a-z0-9_-], must start with [a-z0-9].
        name = (config.name or Path.cwd().resolve().name).lower()
        sanitized = re.sub(r"[^a-z0-9_-]", "", name).lstrip("_-")
        return sanitized or "default"

    @staticmethod
    def resolve_adapter_ports(config: ControllerConfig) -> List[int]:
        ports = []
        for adapter in config.adapters:
            if adapter.type in [ ControllerAdapterType.QUEUE_SUBSCRIBER ]:
                continue
            if hasattr(adapter, "port"):
                ports.append(adapter.port)
        return ports

    @staticmethod
    def resolve_image_kind(config: ControllerConfig) -> ContainerImageKind:
        """Classify the controller runtime as STANDARD / DERIVED / CUSTOM."""
        runtime = config.runtime

        if runtime.image or runtime.build:
            return ContainerImageKind.CUSTOM

        if ControllerImageSpec._has_user_requirements():
            return ContainerImageKind.DERIVED

        return ContainerImageKind.STANDARD

    @staticmethod
    def _has_user_requirements() -> bool:
        path = Path.cwd() / "requirements.txt"
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return True
        return False

class ControllerContainerRuntimeLauncher:
    """Controller lifecycle. Composes a backend ContainerRuntimeBackend."""

    def __init__(self, config: ControllerConfig, backend: ContainerRuntimeBackend, image_kind: ContainerImageKind):
        self.config: ControllerConfig = config
        self._backend: ContainerRuntimeBackend = backend
        self._image_kind: ContainerImageKind = image_kind

    async def launch(self, specs: ControllerRuntimeSpecs, detach: bool) -> None:
        logging.info("Preparing controller container...")

        # STANDARD/DERIVED images expect `bootstrap.sh` to copy /mnt/bootstrap → /workspace
        # at container start. CUSTOM images are caller-baked and need neither.
        if self._image_kind != ContainerImageKind.CUSTOM:
            bundle_path = Path.cwd() / ".build" / "workspace" / ControllerImageSpec.project_name(self.config)
            generate_workspace_bundle(specs, bundle_path)
            self._attach_workspace_volume(bundle_path)

        runtime = await self._backend.provision_runtime(self.config.runtime)

        logging.info("Starting controller container (%s mode)...", "detached" if detach else "foreground")
        await runtime.start(detach)

    async def terminate(self) -> None:
        await self._backend.terminate_runtime(self.config.runtime)

    async def start(self) -> None:
        """Start an existing (already-prepared) controller container in detached mode."""
        runtime = self._backend.resolve_runtime(self.config.runtime)

        if not await runtime.exists():
            raise RuntimeError(
                f"Container '{runtime.params.container_name}' does not exist. "
                "Use `model-compose up` (launch) to create it first."
            )

        if await runtime.is_running():
            logging.info("Container '%s' is already running.", runtime.params.container_name)
            return

        logging.info("Starting controller container '%s'...", runtime.params.container_name)
        await runtime.start(detach=True)

    async def stop(self) -> None:
        """Stop a running controller container without removing it."""
        runtime = self._backend.resolve_runtime(self.config.runtime)

        if not await runtime.exists():
            logging.info("Container '%s' does not exist.", runtime.params.container_name)
            return

        if not await runtime.is_running():
            logging.info("Container '%s' is already stopped.", runtime.params.container_name)
            return

        logging.info("Stopping controller container '%s'...", runtime.params.container_name)
        await runtime.stop()

    def _attach_workspace_volume(self, bundle_path: Path) -> None:
        """Idempotently add the `<bundle>:/mnt/bootstrap:ro` mount to runtime
        volumes. Safe to call multiple times — repeat launchers built from
        the same config see the same mount and re-adding is a no-op."""
        mount_spec = f"{bundle_path}:/mnt/bootstrap:ro"

        if self.config.runtime.volumes is None:
            self.config.runtime.volumes = []

        if mount_spec not in self.config.runtime.volumes:
            self.config.runtime.volumes.append(mount_spec)

