from __future__ import annotations

from abc import abstractmethod
from typing import Any, Awaitable, Callable, Dict, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig
from mindor.dsl.schema.runtime.impl.common import RuntimeRestartBackoff, RuntimeRestartConfig, RuntimeRestartPolicy
from mindor.dsl.schema.logger import ConsoleLoggerConfig, LoggerType
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import ComponentInstances, create_component
from mindor.core.foundation.variable.time import parse_time
from mindor.core.runtime.manager import RuntimeManager
from mindor.core.foundation.runtime.ipc_proxy import IpcRuntimeProxy
from mindor.core.foundation.runtime.ipc_worker import IpcRuntimeWorker
from mindor.core.logger import logging, create_logger, LoggerInstances
import asyncio, time

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

        # Serialize session start/stop so `run()` never observes a half-replaced
        # (_channel, _proxy) pair during restart.
        self._session_lock: asyncio.Lock = asyncio.Lock()

        # `_restart_gaveup` is read by `run()` to short-circuit requests
        # against a dead manager; attempt counters live inside the restart task.
        self._restart_config: RuntimeRestartConfig = component_config.runtime.restart
        self._restart_task: Optional[asyncio.Task] = None
        self._restart_gaveup: bool = False

    async def start(self) -> None:
        # Entire bring-up stays under the lock so concurrent `start()` calls
        # can't both complete `_start_session()` and orphan each other.
        async with self._session_lock:
            if self._proxy is not None:
                raise RuntimeError(f"worker '{self.worker_id}' is already started")

            self._restart_gaveup = False
            await self._start_session()

            if self._restart_config.policy != RuntimeRestartPolicy.NO:
                self._restart_task = asyncio.create_task(self._restart_on_close())

    async def stop(self) -> None:
        # Cancel the restart loop first so it doesn't try to restart the
        # session we're about to tear down.
        if self._restart_task is not None:
            self._restart_task.cancel()

            try:
                await self._restart_task
            except (asyncio.CancelledError, Exception):
                pass

            self._restart_task = None

        async with self._session_lock:
            await self._stop_session()

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def run(
        self,
        action_id: str,
        run_id: str,
        input_data: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Any:
        if self._restart_gaveup:
            raise ConnectionError(f"worker '{self.worker_id}' is unavailable")

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
        counter, lazy session start)."""
        proxy = self._proxy

        if proxy is None:
            raise ConnectionError(f"worker '{self.worker_id}' is not available")

        return await proxy.run(action_id, run_id, input_data, on_event=on_event)

    async def _start_session(self) -> None:
        """Open a channel and start the IPC proxy. Caller holds `_session_lock`.

        Catches `BaseException` so a cancel mid-`_launch`/`_create_proxy`/
        `_proxy.start()` still releases the partially-allocated channel —
        otherwise cancel would leak the subprocess/container/pod we just
        brought up. The cleanup `_shutdown()` is shielded for the same reason
        as `_stop_session`: a cancel propagating through here must not abort
        the OS-level teardown half-way."""
        try:
            self._channel = await self._launch()
            self._proxy = self._create_proxy(self._channel)

            await self._proxy.start()
        except BaseException:
            if self._channel is not None:
                try:
                    await asyncio.shield(self._shutdown(self._channel))
                except Exception:
                    pass

                self._channel = None

            self._proxy = None

            raise

    async def _stop_session(self) -> None:
        """Stop the IPC proxy and close the channel. Caller holds `_session_lock`.

        `_proxy.stop()` and `_shutdown()` are shielded so a cancel mid-cleanup
        can't abort the subprocess/container shutdown half-way and leak OS
        resources. The outer `CancelledError` still propagates after both have
        run."""
        try:
            if self._proxy is not None:
                try:
                    await asyncio.shield(self._proxy.stop())
                except Exception:
                    pass
                finally:
                    self._proxy = None
        finally:
            if self._channel is not None:
                try:
                    await asyncio.shield(self._shutdown(self._channel))
                except Exception:
                    pass
                finally:
                    self._channel = None

    async def _restart_on_close(self) -> None:
        """Watch for IPC session death and bring a fresh session back up.

        Lives for the duration of the manager and runs one relaunch cycle each
        time the current proxy's `_closed_event` latches. Exits when the manager
        is stopped, or when attempts exceed the configured ceiling."""
        window = max(parse_time(self._restart_config.window), 1.0)
        max_attempt_count = self._restart_config.max_attempt_count

        window_started_at: Optional[float] = None
        attempts = 0

        try:
            while True:
                proxy = self._proxy

                if proxy is None:
                    return

                await proxy.wait_until_closed()

                # Anything but a manager-initiated stop (worker crash, transport
                # drop, worker-side sys.exit) counts as a crash.
                if proxy.stop_requested and self._restart_config.policy != RuntimeRestartPolicy.ALWAYS:
                    return

                logging.warning("Worker '%s' session closed", self.worker_id)

                # Retry loop for THIS crash — keep trying until a relaunch
                # succeeds or the attempt budget runs out.
                while True:
                    now = time.monotonic()
                    attempts += 1

                    if window_started_at is None or (now - window_started_at) > window:
                        window_started_at = now
                        attempts = 1

                    if max_attempt_count > 0 and attempts > max_attempt_count:
                        self._restart_gaveup = True

                        logging.error(
                            "Worker '%s' restart giving up: attempts exhausted (%d) within %.0fs",
                            self.worker_id, max_attempt_count, window,
                        )

                        return

                    delay = self._resolve_restart_delay(attempts)

                    if max_attempt_count > 0:
                        logging.info(
                            "Worker '%s' restart attempt %d/%d in %.1fs",
                            self.worker_id, attempts, max_attempt_count, delay,
                        )
                    else:
                        logging.info(
                            "Worker '%s' restart attempt %d in %.1fs",
                            self.worker_id, attempts, delay,
                        )

                    if delay > 0.0:
                        await asyncio.sleep(delay)

                    try:
                        async with self._session_lock:
                            await self._stop_session()
                            await self._start_session()
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logging.warning(
                            "Worker '%s' restart attempt failed: %s",
                            self.worker_id, str(e) or type(e).__name__,
                        )
                        continue

                    logging.info("Worker '%s' restarted successfully", self.worker_id)
                    break

                # Give the next crash a fresh attempt budget.
                window_started_at = None
                attempts = 0
        except asyncio.CancelledError:
            pass

    def _resolve_restart_delay(self, attempt: int) -> float:
        delay = parse_time(self._restart_config.delay)

        if self._restart_config.backoff == RuntimeRestartBackoff.EXPONENTIAL:
            delay = delay * (2 ** (attempt - 1))

        delay = min(delay, parse_time(self._restart_config.max_delay))

        return max(delay, 0.0)

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
