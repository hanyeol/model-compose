from __future__ import annotations

from abc import abstractmethod
from typing import Any, Awaitable, Callable, Dict, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig
from mindor.dsl.schema.logger import ConsoleLoggerConfig, LoggerType
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import ComponentInstances, create_component
from mindor.core.runtime.manager import RuntimeManager
from mindor.core.foundation.runtime.ipc_proxy import IpcRuntimeProxy
from mindor.core.foundation.runtime.ipc_worker import IpcRuntimeWorker
from mindor.core.logger import logging, create_logger, LoggerInstances
import asyncio

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
        self.logger = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def _start(self) -> None:
        self._loop = asyncio.get_event_loop()

        # Worker processes inherit no logger, so route `logging.*` to stderr
        # which the parent captures as the worker's log channel.
        if not LoggerInstances:
            self.logger = create_logger(f"{self.worker_id}-logger", ConsoleLoggerConfig(type=LoggerType.CONSOLE), daemon=False)
            await self.logger.start()

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
        try:
            if self.component is not None:
                try:
                    await self.component.stop()
                finally:
                    await self.component.teardown()
        finally:
            if self.logger is not None:
                await self.logger.stop()
                self.logger = None

    async def _execute_task(
        self,
        payload: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Any:
        return await self.component.run(
            payload["action_id"],
            payload["run_id"],
            payload["input"],
            on_event=on_event,
        )

    @abstractmethod
    async def _send_message(self, message: bytes) -> None:
        """Send a framed message over the backend-specific transport."""

    @abstractmethod
    async def _recv_message(self) -> Optional[bytes]:
        """Receive the next framed message, or `None` when the transport is closed."""

    @abstractmethod
    def _close_transport(self) -> None:
        """Close the backend-specific transport. Counterpart to the transport open in `_start`."""

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

        self.on_call = self._handle_component_call

        self.component_config: ComponentConfig = component_config
        self.global_configs: ComponentGlobalConfigs = global_configs
        self.channel: Any = channel

    async def _start(self) -> None:
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

    async def run(
        self,
        action_id: str,
        run_id: str,
        input_data: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Any:
        return await self.request({
            "action_id": action_id,
            "run_id": run_id,
            "input": input_data,
        }, on_event=on_event)

    async def _handle_component_call(self, call_id: str, payload: Dict[str, Any]) -> Any:
        component_id = payload.get("component_id")
        action_id = payload.get("action_id")
        run_id = payload.get("run_id")
        input_data = payload.get("input") or {}

        if not isinstance(component_id, str):
            raise ValueError("CALL payload missing 'component_id'")

        target = ComponentInstances.get(component_id)
        if target is None:
            raise LookupError(
                f"Referenced component '{component_id}' is not registered in the parent process"
            )

        return await target.run(action_id, run_id, input_data)

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

class ComponentRuntimeManager(RuntimeManager):
    """Component-side lifecycle manager base.

    Follows the docker-compose up/create/start/stop/down model:

    - ``setup()``   — image pull/build, venv bootstrap, container create.
                      Everything a subsequent ``start()`` needs to be instant.
                      Idempotent and expensive; survives across start/stop.
    - ``start()``   — bring the pre-provisioned runtime up: start the container
                      (or spawn the subprocess), open the IPC channel, wrap it
                      in a ``ComponentRuntimeProxy``.
    - ``stop()``    — shut down the IPC session and stop the container, but
                      keep the provisioned artifacts so a later ``start()`` is
                      cheap.
    - ``teardown()`` — remove the container (and derived image if any), undoing
                       what ``setup()`` provisioned.
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
            if self._channel is not None:
                try:
                    await self._shutdown(self._channel)
                except Exception:
                    pass
                self._channel = None
            raise

    async def stop(self) -> None:
        if self._proxy is not None:
            try:
                await self._proxy.stop()
            except Exception:
                pass

            self._proxy = None

        if self._channel is not None:
            try:
                await self._shutdown(self._channel)
            except Exception:
                pass
            self._channel = None

    async def run(
        self,
        action_id: str,
        run_id: str,
        input_data: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Any:
        return await self._run(action_id, run_id, input_data, on_event)

    async def _run(
        self,
        action_id: str,
        run_id: str,
        input_data: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Any:
        """Dispatch one request through the IPC proxy. Subclasses override to
        wrap the call with per-request lifecycle logic (idle timer, active
        counter, lazy session bring-up)."""
        return await self._proxy.run(action_id, run_id, input_data, on_event=on_event)

    @abstractmethod
    async def _launch(self) -> Any:
        """Bring the pre-provisioned runtime up and open the IPC channel.
        Returns the channel. Called at ``start()``."""

    @abstractmethod
    async def _shutdown(self, channel: Any) -> None:
        """Close the channel and stop the running runtime. Counterpart to
        ``_launch``. Must not remove provisioned artifacts — that is
        ``teardown()``'s job. May be called after a partial launch."""

    @abstractmethod
    def _create_proxy(self, channel: Any) -> ComponentRuntimeProxy:
        """Wrap `channel` in the backend-specific proxy subclass."""
