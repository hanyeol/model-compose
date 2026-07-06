from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
from mindor.core.component.runtime.base.ipc_worker import IpcRuntimeWorker
from mindor.core.runtime.common import ContainerRuntimeBackend, ContainerRuntimeConfig
from mindor.core.logger import logging
from mindor.version import __version__
import asyncio, re

class ComponentContainerSpec:
    """Component-image conventions shared by component backends."""

    @staticmethod
    def standard_image_tag() -> str:
        return f"mindor/component:{__version__}"

    @staticmethod
    def derived_image_tag(worker_id: str) -> str:
        return f"mindor/component-{ComponentContainerSpec.project_name(worker_id)}:{__version__}"

    @staticmethod
    def custom_image_tag(worker_id: str) -> str:
        return f"mindor/component-{ComponentContainerSpec.project_name(worker_id)}:latest"

    @staticmethod
    def default_container_name(worker_id: str) -> str:
        return f"mindor-component-{worker_id}"

    @staticmethod
    def image_assets_dir() -> Path:
        return Path(__file__).resolve().parent / "container" / "assets"

    @staticmethod
    def project_name(worker_id: str) -> str:
        sanitized = re.sub(r"[^a-z0-9_-]", "", worker_id.lower()).strip("_-")
        return sanitized or "default"

class ComponentRuntimeWorker(IpcRuntimeWorker):
    """Component-side IPC worker base.

    Hosts an embedded-runtime component instance. Subclasses plug in the
    transport-specific `_send_message` / `_recv_message` / `_close_transport`.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id)

        self.component_config: ComponentConfig = component_config
        self.global_configs: ComponentGlobalConfigs = global_configs
        self.component = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def _start(self) -> None:
        self._loop = asyncio.get_event_loop()

        embedded_config = self.component_config.model_copy(deep=True)
        embedded_config.runtime = EmbeddedRuntimeConfig(type="embedded")

        self.component = create_component(
            self.worker_id,
            embedded_config,
            self.global_configs,
            daemon=True,
        )
        await self.component.setup()
        await self.component.start()

    async def _stop(self) -> None:
        if self.component is not None:
            try:
                await self.component.stop()
            finally:
                await self.component.teardown()

    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        return await self.component.run(
            payload["action_id"],
            payload["run_id"],
            payload["input"],
        )

    @abstractmethod
    async def _send_message(self, message: bytes) -> None: ...

    @abstractmethod
    async def _recv_message(self) -> Optional[bytes]: ...

    @abstractmethod
    def _close_transport(self) -> None: ...

class ComponentRuntimeProxy(IpcRuntimeProxy):
    """Component-side IPC proxy base — remote worker's local representative.

    Holds the component config / global configs (needed for START handshake
    payload) and the concrete `channel`. Subclasses supply the transport
    adapter (`_send_message` / `_recv_message`) over that channel.

    The `_start()` template method performs the IPC handshake: send START →
    wait for STATUS(ready) → spawn response task.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        channel: Any,
    ):
        super().__init__(component_id)

        self.component_config: ComponentConfig = component_config
        self.global_configs: ComponentGlobalConfigs = global_configs
        self.channel: Any = channel

    async def _start(self) -> None:
        self._loop = asyncio.get_event_loop()

        await self._send_start_message()
        await self._wait_for_ready()

        self._response_task = asyncio.create_task(self._handle_responses())

    async def _stop(self) -> None:
        try:
            await self._send_stop_message()
        except Exception:
            pass

        if self._response_task is not None:
            try:
                await asyncio.wait_for(self._response_task, timeout=self._stop_timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._response_task.cancel()

    async def run(self, action_id: str, run_id: str, input_data: Dict[str, Any]) -> Any:
        return await self.request({
            "action_id": action_id,
            "run_id": run_id,
            "input": input_data,
        })

    async def _send_start_message(self) -> None:
        """Attach the component config / global configs to the START message.

        Override to skip when the config reaches the worker out-of-band (e.g.
        multiprocessing `spawn` pickles it into the child's args).
        """
        await super()._send_start_message(payload={
            "component_id": self.worker_id,
            "component_config": self.component_config.model_dump(mode="json"),
            "global_configs": self.global_configs.model_dump(mode="json"),
        })

class ComponentRuntimeManager:
    """Component-side lifecycle manager base.

    Spawns the child runtime (container / subprocess / venv), prepares the IPC
    channel, wraps it in a `ComponentRuntimeProxy`, and orchestrates the
    start/stop sequence. Owns the runtime and the channel; delegates all IPC
    to the proxy.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        self.worker_id: str = component_id
        self.component_config: ComponentConfig = component_config
        self.global_configs: ComponentGlobalConfigs = global_configs

        self._proxy: Optional[ComponentRuntimeProxy] = None
        self._channel: Optional[Any] = None

    async def start(self) -> None:
        try:
            self._channel = await self._launch()
            self._proxy = self._create_proxy(self._channel)
            await self._proxy.start()
        except Exception:
            await self._teardown()
            raise

    async def stop(self) -> None:
        if self._proxy is not None:
            try:
                await self._proxy.stop()
            except Exception:
                pass
            self._proxy = None

        await self._teardown()

    async def run(self, action_id: str, run_id: str, input_data: Dict[str, Any]) -> Any:
        if self._proxy is None:
            raise RuntimeError(f"Manager '{self.worker_id}' is not started")

        return await self._proxy.run(action_id, run_id, input_data)

    async def _teardown(self) -> None:
        """Shut down the runtime and channel. Called on both failed start and
        normal stop. Idempotent."""
        if self._channel is not None:
            try:
                await self._shutdown(self._channel)
            except Exception:
                pass
            self._channel = None

    @abstractmethod
    async def _launch(self) -> Any:
        """Prepare the runtime, start it, and open the IPC channel. Returns the
        channel. Called once at `start()`."""

    @abstractmethod
    async def _shutdown(self, channel: Any) -> None:
        """Close the channel and tear down the runtime. Counterpart to
        `_launch`. May be called after a partial launch."""

    @abstractmethod
    def _create_proxy(self, channel: Any) -> ComponentRuntimeProxy:
        """Wrap `channel` in the backend-specific proxy subclass."""

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

    async def _launch(self) -> Any:
        # Provision the image and container, then attach the IPC channel.
        self._runtime = await self._backend.provision_runtime()
        return await self._attach_channel()

    async def _shutdown(self, channel: Any) -> None:
        try:
            self._detach_channel(channel)
        except Exception:
            pass

        if self._runtime is not None:
            try:
                await self._runtime.stop()
                await self._runtime.remove(force=True)
            except Exception as e:
                logging.warning("Error stopping container for '%s': %s", self.worker_id, e)
            self._runtime = None

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
