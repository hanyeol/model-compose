from __future__ import annotations

from typing import Any, BinaryIO, Dict, List, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig
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
from mindor.core.foundation.containers.docker import DockerContainerOptions
from mindor.core.runtime.docker import DockerRuntime, DockerRuntimeBackend
from mindor.core.utils.channels.docker_attach import DockerAttachChannel
from pathlib import Path
import asyncio

class ComponentDockerRuntimeBackend(DockerRuntimeBackend):
    """Image + container preparer for a component runtime."""
    def __init__(
        self,
        worker_id: str,
        runtime_config: DockerRuntimeConfig,
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

    def _resolve_container_options(self) -> DockerContainerOptions:
        options = super()._resolve_container_options()

        if self.runtime_config.command is None and self.runtime_config.entrypoint is None:
            options.entrypoint = [ "python", "-m", "mindor.core.component.runtime.docker" ]

        return options

    def _image_assets_dir(self) -> Path:
        return ComponentContainerSpec.image_assets_dir()

    def _standard_image_tag(self) -> str:
        return ComponentContainerSpec.standard_image_tag()

    def _derived_image_tag(self) -> str:
        return ComponentContainerSpec.derived_image_tag(self.worker_id)

    def _custom_image_tag(self) -> str:
        return ComponentContainerSpec.custom_image_tag(self.worker_id)

    def _standard_image_command(self) -> List[str]:
        return [ "python", "-m", "mindor.core.component.runtime.docker" ]

    def _container_create_options(self) -> Dict[str, Any]:
        # tty=False so the daemon emits stdout/stderr as separate multiplex
        # frames. stdin_open=True keeps the container's stdin attached for
        # IPC writes from the manager.
        return { "tty": False, "stdin_open": True }

class ComponentDockerRuntimeWorker(ComponentRuntimeWorker):
    """Component-side worker that runs inside the docker container.

    Bridges IPC over a file-descriptor pair (typically the duplicated
    stdin/stdout that main() carved off before redirecting fd 0/1 to
    stderr).
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

        # `ipc_in` / `ipc_out` are open binary file objects from os.fdopen.
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

class ComponentDockerRuntimeProxy(ComponentRuntimeProxy):
    """Docker attach-based IPC proxy.

    Bridges the `DockerAttachChannel` (sync) into async `_send_message` /
    `_recv_message` via `run_in_executor`.
    """
    _channel: DockerAttachChannel

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._channel.recv)

class ComponentDockerRuntimeManager(ComponentContainerRuntimeManager):
    """Component-side manager: composes a `ComponentDockerRuntimeBackend`
    (image + container lifecycle) with a `ComponentDockerRuntimeProxy` over a
    `DockerAttachChannel` to the container's stdin/stdout.

    No bind-mount, no host socket, no uid mapping — IPC travels over the
    docker daemon's attach stream, which works uniformly on Linux native
    daemons and macOS Docker Desktop.
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

        self._runtime: Optional[DockerRuntime] = None

    def _create_backend(
        self,
        component_id: str,
        runtime_config: DockerRuntimeConfig,
        image_kind: ContainerImageKind,
        verbose: bool,
    ) -> ComponentDockerRuntimeBackend:
        return ComponentDockerRuntimeBackend(
            worker_id=component_id,
            runtime_config=runtime_config,
            image_kind=image_kind,
            verbose=verbose,
        )

    async def _attach_channel(self, loop: asyncio.AbstractEventLoop) -> DockerAttachChannel:
        # Attach to stdin/stdout/stderr BEFORE starting so we never miss the
        # worker's STATUS(ready) message — the attach socket is the only way
        # to receive IPC traffic.
        channel = await loop.run_in_executor(None, self._open_attach_channel)
        # Now start the container; the entrypoint will read from stdin.
        await self._runtime.start(detach=True)
        return channel

    def _close_channel(self, channel: DockerAttachChannel) -> None:
        channel.close()

    def _create_proxy(self, channel: DockerAttachChannel) -> ComponentDockerRuntimeProxy:
        proxy = ComponentDockerRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            channel,
        )
        # Propagate the timeouts to the proxy's IPC base.
        proxy._start_timeout = self._start_timeout
        proxy._stop_timeout = self._stop_timeout
        return proxy

    def _open_attach_channel(self) -> DockerAttachChannel:
        """Open a bidirectional attach channel to the container's
        stdin/stdout/stderr stream via the daemon's attach socket."""
        container = self._runtime.get_container()
        sock = container.attach_socket(params={
            "stdin": 1,
            "stdout": 1,
            "stderr": 1,
            "stream": 1,
        })
        return DockerAttachChannel(sock)

def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.docker`."""
    channel = IpcStdioChannel()
    channel.setup()
    channel.run(ComponentDockerRuntimeWorker)

if __name__ == "__main__":
    main()
