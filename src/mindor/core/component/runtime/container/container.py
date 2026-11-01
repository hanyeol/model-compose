from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import ComponentRuntimeManager
from mindor.core.runtime.container import ContainerRuntimeBackend, ContainerRuntimeConfig
from mindor.core.logger import logging
from mindor.version import __version__
import re

class ComponentContainerSpec:
    """Component-image conventions shared by container-backed component backends."""

    @staticmethod
    def standard_image_tag() -> str:
        return f"mindor/component:{__version__}"

    def derived_image_tag(self, worker_id: str) -> str:
        return f"mindor/component-{self.project_name(worker_id)}:{__version__}"

    def custom_image_tag(self, worker_id: str) -> str:
        return f"mindor/component-{self.project_name(worker_id)}:latest"

    @staticmethod
    def default_container_name(worker_id: str) -> str:
        return f"mindor-component-{worker_id}"

    @staticmethod
    def image_assets_dir() -> Path:
        return Path(__file__).resolve().parent / "assets"

    @staticmethod
    def project_name(worker_id: str) -> str:
        name = worker_id.lower()
        name = re.sub(r"[^a-z0-9_-]", "", name).strip("_-")

        return name or "default"

class ComponentContainerRuntimeManager(ComponentRuntimeManager):
    """Manager for container-backed component runtimes (Docker / Apple)."""
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        verbose: bool = False,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._backend: ContainerRuntimeBackend = self._create_backend(component_id, component_config.runtime, verbose)
        self._runtime: Optional[Any] = None

    async def _setup(self) -> None:
        # Provision image + container (both potentially slow — pull/build,
        # layer unpack, container create). Done at setup() so a subsequent
        # start() only has to attach the IPC channel.
        self._runtime = await self._backend.provision_runtime()

    async def _teardown(self) -> None:
        # Remove the container and drop any derived image this manager built.
        # The runtime object held on self is now stale either way.
        try:
            await self._backend.teardown_runtime()
        finally:
            self._runtime = None

    async def _launch(self) -> Any:
        # Container is already created by setup(). Attaching the IPC channel
        # also starts the container (see docker/apple backends).
        return await self._attach_channel()

    async def _shutdown(self, channel: Any) -> None:
        try:
            self._detach_channel(channel)
        except Exception:
            pass

        if self._runtime is not None:
            try:
                await self._runtime.stop()
            except Exception as e:
                logging.warning("Error stopping container for '%s': %s", self.worker_id, e)

    @abstractmethod
    def _create_backend(
        self,
        component_id: str,
        runtime_config: ContainerRuntimeConfig,
        verbose: bool,
    ) -> ContainerRuntimeBackend:
        """Backend factory — supplied by the concrete Docker / Apple facade subclass."""

    @abstractmethod
    async def _attach_channel(self) -> Any:
        """Attach the IPC channel and ensure the container is running."""

    @abstractmethod
    def _detach_channel(self, channel: Any) -> None:
        """Close the backend-specific IPC channel."""
