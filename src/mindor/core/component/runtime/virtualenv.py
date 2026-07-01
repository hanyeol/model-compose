from __future__ import annotations

from typing import Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import (
    ComponentRuntimeLauncher,
    ComponentRuntimeProxy,
    ComponentRuntimeWorker,
)
from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType, IpcStartPayload
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.runtime.virtualenv import VirtualEnvRuntime, VirtualEnvRuntimeParams
from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel
import asyncio, os, sys


class ComponentVirtualEnvRuntimeWorker(ComponentRuntimeWorker):
    """Component-side worker that runs inside the venv interpreter.

    Bridges IPC messages over a `SubprocessPipeChannel`.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        channel: SubprocessPipeChannel,
    ):
        super().__init__(component_id, component_config, global_configs)
        self.channel = channel

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self.channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self.channel.recv)

    def _close_transport(self) -> None:
        self.channel.close()


class ComponentVirtualEnvRuntimeProxy(ComponentRuntimeProxy):
    """SubprocessPipeChannel-based IPC proxy for venv-spawned workers."""
    _channel: SubprocessPipeChannel

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._channel.recv)


class ComponentVirtualEnvRuntimeLauncher(ComponentRuntimeLauncher):
    """Launcher: spawns a `VirtualEnvRuntime` child over a pipe pair and
    wraps the parent's ends in a `ComponentVirtualEnvRuntimeProxy`.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id, component_config, global_configs)

        self.params = self._resolve_runtime_params(component_config.runtime)

        self._runtime: Optional[VirtualEnvRuntime] = None

    async def _prepare_channel(self) -> SubprocessPipeChannel:
        # Create the pipe pair before spawning so we can hand the child its fds.
        request_r,  request_w  = os.pipe()
        response_r, response_w = os.pipe()

        self._runtime = VirtualEnvRuntime(
            worker_id=self.worker_id,
            worker_module="mindor.core.component.runtime.virtualenv",
            params=self.params,
        )

        try:
            await self._runtime.start(
                pass_fds=(request_r, response_w),
                env_overrides={
                    "MINDOR_VENV_REQUEST_FD":  str(request_r),
                    "MINDOR_VENV_RESPONSE_FD": str(response_w),
                },
            )
        finally:
            # The child duplicates its fds; the parent should hold only its own ends.
            os.close(request_r)
            os.close(response_w)

        # Parent uses: read responses on response_r, write requests on request_w.
        return SubprocessPipeChannel(request_fd=response_r, response_fd=request_w)

    def _create_proxy(self, channel: SubprocessPipeChannel) -> ComponentVirtualEnvRuntimeProxy:
        proxy = ComponentVirtualEnvRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            channel,
        )
        proxy._start_timeout = self.params.start_timeout
        proxy._stop_timeout = self.params.stop_timeout
        return proxy

    async def _teardown_runtime(self) -> None:
        if self._runtime is not None:
            await self._runtime.stop()
            self._runtime = None

    def _resolve_runtime_params(self, config: VirtualEnvRuntimeConfig) -> VirtualEnvRuntimeParams:
        return VirtualEnvRuntimeParams(
            driver=config.driver,
            python=config.python,
            path=config.path,
            env=config.env or {},
            start_timeout=parse_duration(config.start_timeout),
            stop_timeout=parse_duration(config.stop_timeout),
        )


def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.virtualenv`."""
    # Ensure stdout/stderr stay attached to the parent as log channels only;
    # the IPC protocol runs on the dedicated fd pair, not on stdout.
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    try:
        request_fd = int(os.environ["MINDOR_VENV_REQUEST_FD"])
        response_fd = int(os.environ["MINDOR_VENV_RESPONSE_FD"])
    except KeyError as e:
        raise RuntimeError(
            f"Missing IPC file descriptor environment variable: {e}. "
            f"This module must be launched by ComponentVirtualEnvRuntimeLauncher."
        ) from e

    channel = SubprocessPipeChannel(
        request_fd=request_fd,
        response_fd=response_fd,
    )

    init_data = channel.recv()
    if init_data is None:
        raise RuntimeError("Expected first IPC message of type 'start', got EOF")
    init = IpcMessage.deserialize(init_data)
    if init.type != IpcMessageType.START:
        raise RuntimeError(
            f"Expected first IPC message of type 'start', got: {init.type!r}"
        )

    payload = IpcStartPayload.model_validate(init.payload or {})

    worker = ComponentVirtualEnvRuntimeWorker(
        payload.component_id,
        payload.component_config,
        payload.global_configs,
        channel,
    )

    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
