from __future__ import annotations

from typing import Dict, List, Optional
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.logger import logging
from mindor.dsl.schema.runtime.remote import SshRemoteTransportConfig
from mindor.core.runtime.transport.ssh import SshRuntimeTransport
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from ..common import CommonRuntime
import shlex

class RemoteProcessRuntime(CommonRuntime):
    """Lifecycle wrapper around a worker process running on a remote host.

    Mirrors ``LocalProcessRuntime`` for the ``config.remote`` case: owns a
    single SSH transport and one exec channel that carries the IPC stream.
    The worker binary / Python environment on the remote side is assumed to
    already be provisioned by the user — this runtime only launches a command
    and wires stdin/stdout to the channel.

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

    async def start(self, env: Optional[Dict[str, str]] = None) -> SshExecChannel:
        logging.info("process: ssh connecting to %s...", self._transport.host)

        await self._transport.connect()

        # Resolve the remote python executable through an interactive shell
        # so pyenv / venv activation / user profile scripts have a chance to
        # run. The returned path is the real binary (not a shim), so the
        # non-interactive exec channel below can invoke it directly.
        executable = await self._transport.resolve_executable(
            working_dir=self._transport.working_dir,
        )

        logging.debug("process: using remote python at %s", executable)

        command = self._build_remote_command(executable, env)

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

    def _build_remote_command(self, executable: str, env: Optional[Dict[str, str]]) -> str:
        # OpenSSH servers often reject SetEnv for anything not whitelisted in
        # sshd_config, so prefix VAR=value inline. `cd` honors working_dir when
        # set by the transport. `exec` replaces the shell so signals reach the
        # Python worker directly.
        commands: List[str] = []

        if self._transport.working_dir:
            commands.append(f"cd {shlex.quote(self._transport.working_dir)}")

        env = { **(self.config.env or {}), **(env or {}) }
        env_prefix = "".join(f"{name}={shlex.quote(str(value))} " for name, value in env.items())
        commands.append(
            f"{env_prefix}exec {shlex.quote(executable)} -m {shlex.quote(self.worker_module)}"
        )

        return " && ".join(commands)
