from typing import List, Optional, Tuple
from abc import abstractmethod
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.controller.adapter.impl.types import ControllerAdapterType
from mindor.core.runtime.common import ContainerImageKind, ContainerRuntimeBackend
from mindor.core.logger import logging
from mindor.version import __version__
from .base.specs import ControllerRuntimeSpecs
from .base.workspace import generate_workspace_bundle
from pathlib import Path
import re

class ControllerContainerSpec:
    """Controller-image conventions shared by Docker/Apple backends."""

    @staticmethod
    def standard_image_tag() -> str:
        return f"mindor/controller:{__version__}"

    @staticmethod
    def derived_image_tag(controller_name: Optional[str]) -> str:
        return f"mindor/controller-{ControllerContainerSpec.project_name(controller_name)}:{__version__}"

    @staticmethod
    def custom_image_tag(controller_name: Optional[str]) -> str:
        return f"mindor/controller-{ControllerContainerSpec.project_name(controller_name)}:latest"

    @staticmethod
    def default_container_name(controller_name: Optional[str]) -> str:
        return f"mindor-controller-{ControllerContainerSpec.project_name(controller_name)}"

    @staticmethod
    def standard_image_command() -> List[str]:
        return [ "python", "-m", "mindor.cli.compose", "up" ]

    @staticmethod
    def image_assets_dir() -> Path:
        return Path(__file__).resolve().parent / "container" / "assets"

    @staticmethod
    def project_name(controller_name: Optional[str]) -> str:
        # Follows docker-compose: compose `name:` wins, else sanitized cwd basename.
        # Sanitization rule: lowercased, only [a-z0-9_-], must start with [a-z0-9].
        name = (controller_name or Path.cwd().resolve().name).lower()
        sanitized = re.sub(r"[^a-z0-9_-]", "", name).strip("_-")
        return sanitized or "default"

    @staticmethod
    def resolve_service_ports(config: ControllerConfig) -> List[Tuple[Optional[str], int]]:
        """Ports this controller publishes to the host, each paired with the
        host IP to bind. `None` host_ip means "all interfaces". Preserves the
        user's `host` config so container publish keeps the same exposure
        semantics as local execution (default `127.0.0.1` → loopback only)."""
        ports: List[Tuple[Optional[str], int]] = []

        for adapter in config.adapters:
            if adapter.type in (ControllerAdapterType.QUEUE_SUBSCRIBER, ):
                continue
            if hasattr(adapter, "port"):
                ports.append((getattr(adapter, "host", None), adapter.port))

        webui_port = getattr(config.webui, "port", None)
        if webui_port:
            ports.append((getattr(config.webui, "host", None), webui_port))

        return ports

class ControllerContainerRuntimeManager:
    """Controller lifecycle. Composes a backend ContainerRuntimeBackend."""
    def __init__(self, config: ControllerConfig, verbose: bool = False):
        self.config: ControllerConfig = config

        self._image_kind: ContainerImageKind = self._resolve_image_kind(config)
        self._backend: ContainerRuntimeBackend = self._create_backend(config, self._image_kind, verbose)

    async def launch(self, specs: ControllerRuntimeSpecs, detach: bool) -> None:
        logging.info("Preparing controller container...")

        # STANDARD/DERIVED images expect `bootstrap.sh` to copy /mnt/bootstrap → /workspace
        # at container start. CUSTOM images are caller-baked and need neither.
        if self._image_kind != ContainerImageKind.CUSTOM:
            bundle_path = Path.cwd() / ".build" / "workspace" / ControllerContainerSpec.project_name(self.config.name)
            generate_workspace_bundle(specs, bundle_path)
            self._attach_workspace_volume(bundle_path)

        runtime = await self._backend.provision_runtime()

        logging.info("Starting controller container (%s mode)...", "detached" if detach else "foreground")
        await runtime.start(detach)

    async def terminate(self) -> None:
        await self._backend.teardown_runtime()

    async def start(self) -> None:
        """Start an existing (already-prepared) controller container in detached mode."""
        runtime = self._backend.resolve_runtime()

        if not await runtime.exists():
            raise RuntimeError(
                f"Container '{runtime.container_name}' does not exist. "
                "Use `model-compose up` (launch) to create it first."
            )

        if await runtime.is_running():
            logging.info("Container '%s' is already running.", runtime.container_name)
            return

        logging.info("Starting controller container '%s'...", runtime.container_name)
        await runtime.start(detach=True)

    async def stop(self) -> None:
        """Stop a running controller container without removing it."""
        runtime = self._backend.resolve_runtime()

        if not await runtime.exists():
            logging.info("Container '%s' does not exist.", runtime.container_name)
            return

        if not await runtime.is_running():
            logging.info("Container '%s' is already stopped.", runtime.container_name)
            return

        logging.info("Stopping controller container '%s'...", runtime.container_name)
        await runtime.stop()

    @abstractmethod
    def _create_backend(
        self,
        config: ControllerConfig,
        image_kind: ContainerImageKind,
        verbose: bool,
    ) -> ContainerRuntimeBackend:
        """Backend factory — supplied by the concrete Docker / Apple facade subclass."""

    def _resolve_image_kind(self, config: ControllerConfig) -> ContainerImageKind:
        """Classify the controller runtime as STANDARD / DERIVED / CUSTOM."""
        runtime = config.runtime

        if runtime.image or runtime.build:
            return ContainerImageKind.CUSTOM

        if self._has_derived_context():
            return ContainerImageKind.DERIVED

        return ContainerImageKind.STANDARD

    def _has_derived_context(self) -> bool:
        return (
            self._has_meaningful_lines(Path.cwd() / "requirements.txt")
            or (Path.cwd() / "setup.sh").is_file()
        )

    @staticmethod
    def _has_meaningful_lines(path: Path) -> bool:
        if not path.is_file():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return True
        return False

    def _attach_workspace_volume(self, bundle_path: Path) -> None:
        """Idempotently add the `<bundle>:/mnt/bootstrap:ro` mount to runtime
        volumes. Safe to call multiple times — repeat managers built from
        the same config see the same mount and re-adding is a no-op."""
        mount_spec = f"{bundle_path}:/mnt/bootstrap:ro"

        if self.config.runtime.volumes is None:
            self.config.runtime.volumes = []

        if mount_spec not in self.config.runtime.volumes:
            self.config.runtime.volumes.append(mount_spec)
