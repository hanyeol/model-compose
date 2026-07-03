from __future__ import annotations

from typing import Any, BinaryIO, Dict, List, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import AppleContainerRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import (
    ComponentContainerRuntimeManager,
    ComponentContainerSpec,
    ComponentRuntimeProxy,
    ComponentRuntimeWorker,
)
from mindor.core.component.runtime.base.ipc_stdio_channel import IpcStdioChannel
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.runtime.common import ContainerImageKind
from mindor.core.runtime.apple_container import (
    AppleContainerRuntime,
    AppleContainerRuntimeBackend,
    AppleContainerRuntimeParams,
)
from mindor.core.utils.channels.apple_container_attach import AppleContainerAttachChannel
from pathlib import Path
import asyncio

class ComponentAppleContainerRuntimeBackend(AppleContainerRuntimeBackend):
    """Image + container preparer for a component runtime on Apple Container."""
    def __init__(
        self,
        worker_id: str,
        runtime_config: AppleContainerRuntimeConfig,
        image_kind: ContainerImageKind,
        verbose: bool = False,
    ):
        super().__init__(runtime_config=runtime_config, image_kind=image_kind, verbose=verbose)

        self.worker_id: str = worker_id

    def _default_image_tag(self) -> str:
        if self._image_kind == ContainerImageKind.CUSTOM:
            return self._custom_image_tag()
        if self._image_kind == ContainerImageKind.DERIVED:
            return self._derived_image_tag()
        return self._standard_image_tag()

    def _default_container_name(self) -> str:
        return ComponentContainerSpec.default_container_name(self.worker_id)

    def _resolve_runtime_params(self) -> AppleContainerRuntimeParams:
        params = super()._resolve_runtime_params()

        if params.command is None and params.entrypoint is None:
            params.entrypoint = [ "python", "-m", "mindor.core.component.runtime.apple_container" ]

        return params

    def _image_assets_dir(self) -> Path:
        return ComponentContainerSpec.image_assets_dir()

    def _standard_image_tag(self) -> str:
        return ComponentContainerSpec.standard_image_tag()

    def _derived_image_tag(self) -> str:
        return ComponentContainerSpec.derived_image_tag(self.worker_id)

    def _custom_image_tag(self) -> str:
        return ComponentContainerSpec.custom_image_tag(self.worker_id)

    def _standard_image_command(self) -> List[str]:
        return [ "python", "-m", "mindor.core.component.runtime.apple_container" ]

    def _container_create_options(self) -> Dict[str, Any]:
        # tty=False so the container's stdout/stderr arrive as separate streams
        # under the CLI's attach. stdin_open=True keeps stdin attached for IPC
        # writes from the parent.
        return { "tty": False, "stdin_open": True }


class ComponentAppleContainerRuntimeWorker(ComponentRuntimeWorker):
    """Component-side worker that runs inside the Apple Container.

    Bridges IPC over the container's stdin/stdout file descriptors. The
    parent `container start -a -i <name>` subprocess connects its stdin/
    stdout to the container's stdin/stdout, so the worker just talks to
    its own fd 0/1 (after `main()` carves them off and redirects fd 0/1
    to stderr).
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        ipc_in: BinaryIO,
        ipc_out: BinaryIO,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._ipc_in: BinaryIO = ipc_in
        self._ipc_out: BinaryIO = ipc_out

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._write_line, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._read_line)

    def _write_line(self, message: bytes) -> None:
        self._ipc_out.write(message + b"\n")
        self._ipc_out.flush()

    def _read_line(self) -> Optional[bytes]:
        line = self._ipc_in.readline()
        if not line:
            return None
        return line.rstrip(b"\n")

    def _close_transport(self) -> None:
        for resource in (self._ipc_in, self._ipc_out):
            try:
                resource.close()
            except Exception:
                pass


class ComponentAppleContainerRuntimeProxy(ComponentRuntimeProxy):
    """Apple Container attach-based IPC proxy.

    The `AppleContainerAttachChannel` is async-native (async `send`/`recv`),
    so `_send_message` / `_recv_message` await directly without executor.
    """
    _channel: AppleContainerAttachChannel

    async def _send_message(self, message: bytes) -> None:
        await self._channel.send(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._channel.recv()


class ComponentAppleContainerRuntimeManager(ComponentContainerRuntimeManager):
    """Component-side manager: composes a `ComponentAppleContainerRuntimeBackend`
    with a `ComponentAppleContainerRuntimeProxy` over an
    `AppleContainerAttachChannel` (subprocess stdin/stdout).
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        verbose: bool = False,
    ):
        super().__init__(component_id, component_config, global_configs, verbose)

        self._start_timeout = parse_duration(component_config.runtime.start_timeout)
        self._stop_timeout = parse_duration(component_config.runtime.stop_timeout)

        self._runtime: Optional[AppleContainerRuntime] = None

    def _create_backend(
        self,
        component_id: str,
        runtime_config: AppleContainerRuntimeConfig,
        image_kind: ContainerImageKind,
        verbose: bool,
    ) -> ComponentAppleContainerRuntimeBackend:
        return ComponentAppleContainerRuntimeBackend(
            worker_id=component_id,
            runtime_config=runtime_config,
            image_kind=image_kind,
            verbose=verbose,
        )

    async def _attach_channel(self, loop: asyncio.AbstractEventLoop) -> AppleContainerAttachChannel:
        """Spawn `container start -a -i <name>` and wrap its stdin/stdout as
        the IPC channel. The subprocess is what actually starts the container
        (no separate `runtime.start()` call needed). The subprocess inherits
        stderr as a pipe so the container's logs are captured off the IPC
        stream."""
        process = await asyncio.create_subprocess_exec(
            "container", "start", "-a", "-i", self._runtime.params.container_name,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return AppleContainerAttachChannel(process)

    def _create_proxy(self, channel: AppleContainerAttachChannel) -> ComponentAppleContainerRuntimeProxy:
        proxy = ComponentAppleContainerRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            channel,
        )
        proxy._start_timeout = self._start_timeout
        proxy._stop_timeout = self._stop_timeout
        return proxy


def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.apple_container`."""
    channel = IpcStdioChannel()
    channel.setup()
    channel.run(ComponentAppleContainerRuntimeWorker)


if __name__ == "__main__":
    main()
