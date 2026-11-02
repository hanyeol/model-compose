from __future__ import annotations

from typing import Dict, Optional
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.logger import logging
from mindor.dsl.schema.runtime.remote import SshRemoteTransportConfig
from mindor.core.runtime.transport.ssh import SshRuntimeTransport
from mindor.core.runtime.shell import CommonShell
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from ..common import CommonRuntime

class RemoteProcessRuntime(CommonRuntime):
    """Lifecycle wrapper around a worker process running on a remote host.

    Mirrors ``LocalProcessRuntime`` for the ``config.remote`` case: owns a
    single SSH transport and one exec channel that carries the IPC stream.
    The worker binary / Python environment on the remote side is assumed to
    already be provisioned by the user — this runtime only launches a command
    and wires stdin/stdout to the channel.

    Supports both POSIX (bash/zsh) and PowerShell login shells on the
    remote; the right command dialect is chosen in `start()` by asking the
    remote python for ``platform.system()``.

    Typical flow:
        runtime = RemoteProcessRuntime(remote_config, worker_module, config=config)
        channel = await runtime.start(env=...)
        ...
        await runtime.stop()
    """
    config: ProcessRuntimeConfig

    def __init__(
        self,
        remote_config: SshRemoteTransportConfig,
        worker_module: str,
        config: ProcessRuntimeConfig,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self.worker_module = worker_module

        self._transport: SshRuntimeTransport = SshRuntimeTransport(remote_config)
        self._channel: Optional[SshExecChannel] = None
        self._shell: Optional[CommonShell] = None

    async def start(self, env: Optional[Dict[str, str]] = None) -> SshExecChannel:
        logging.info("process: ssh connecting to %s...", self._transport.host)

        await self._transport.connect()

        self._shell = await self._transport.resolve_remote_shell()

        logging.debug("process: using remote shell dialect %s", self._shell.dialect)

        # Resolve the remote python executable through an interactive shell
        # so pyenv / venv activation / user profile scripts have a chance to
        # run. The returned path is the real binary (not a shim), so the
        # non-interactive exec channel below can invoke it directly.
        executable = await self._transport.evaluate_python_expression(
            "python",
            "__import__('sys').executable",
            working_dir=self._transport.working_dir,
        )

        logging.debug("process: using remote python at %s", executable)

        env = { **(self.config.env or {}), **(env or {}) }
        command = self._shell.launch_module_command(
            executable,
            self.worker_module,
            env,
            self._transport.working_dir,
        )

        logging.info("process: launching remote worker on %s...", self._transport.host)

        self._channel = await self._transport.open_exec_channel(command)

        return self._channel

    async def stop(self) -> None:
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass

            self._channel = None

        await self._transport.close()

    @property
    def channel(self) -> Optional[SshExecChannel]:
        return self._channel
