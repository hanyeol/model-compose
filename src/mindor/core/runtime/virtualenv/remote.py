from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
from mindor.core.runtime.transport.ssh import SshRuntimeTransport, SshBasedRemoteTransportConfig
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from ..common import CommonRuntime
import posixpath, shlex

class RemoteVirtualEnvRuntime(CommonRuntime):
    """Lifecycle wrapper around a venv-isolated Python worker on a remote host.

    Mirrors ``LocalVirtualEnvRuntime`` for the ``config.remote`` case: owns
    one SSH transport and provisions a venv on the remote filesystem by
    piping shell commands over `exec_command`. The remote host must already
    have an installed copy of ``mindor`` that `import mindor` can find
    through the user's interactive shell — this runtime wires the venv to
    that installation via a ``mindor.pth`` file rather than shipping the
    source over SSH.

    Typical flow:
        runtime = RemoteVirtualEnvRuntime(remote_config, worker_id, worker_module, config)
        await runtime.connect()
        await runtime.create_venv()
        await runtime.install_mindor_source()
        await runtime.install_requirements()
        channel = await runtime.start(env=...)
        ...
        await runtime.stop()
    """
    config: VirtualEnvRuntimeConfig

    def __init__(
        self,
        remote_config: SshBasedRemoteTransportConfig,
        worker_id: str,
        worker_module: str,
        config: VirtualEnvRuntimeConfig,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self.worker_id = worker_id
        self.worker_module = worker_module

        self._stop_timeout = parse_time(config.stop_timeout) if config.stop_timeout is not None else None

        self._transport: SshRuntimeTransport = SshRuntimeTransport(remote_config)
        self._channel: Optional[SshExecChannel] = None
        self._executable: Optional[str] = None
        self._venv_path: Optional[str] = None
        self._mindor_source_path: Optional[str] = None

    @property
    def channel(self) -> Optional[SshExecChannel]:
        return self._channel

    async def connect(self) -> None:
        await self._transport.connect()

        self._executable = await self._transport.resolve_executable(
            working_dir=self._transport.working_dir,
        )
        self._venv_path = self._resolve_venv_path()
        self._mindor_source_path = await self._transport.resolve_mindor_source_path(
            self._executable,
            working_dir=self._transport.working_dir,
        )

    async def create_venv(self) -> None:
        """Run ``<executable> -m venv <path>`` on the remote host (idempotent).

        The ``path`` driver is the only supported mode for remote venvs; the
        pyenv driver would need pyenv on the remote, which this runtime does
        not provision.
        """
        if self.config.driver != VirtualEnvDriver.PYTHON:
            raise NotImplementedError(
                f"remote virtualenv only supports driver 'python', got {self.config.driver!r}"
            )

        command = (
            f"test -x {shlex.quote(self._venv_path + '/bin/python')} || "
            f"{shlex.quote(self._executable)} -m venv {shlex.quote(self._venv_path)}"
        )

        logging.info("virtualenv: creating remote venv at %s:%s...", self._transport.host, self._venv_path)

        await self._run_remote_command(command)

    async def install_mindor_source(self) -> None:
        """Write a ``mindor.pth`` file into the remote venv's site-packages
        pointing at the ``mindor`` package directory resolved during
        `connect()`.

        This is the editable-install path on the remote: whatever ``import
        mindor`` resolves to on the remote user's shell is what the venv
        picks up, so there is no byte transfer from host to remote.
        """
        site_packages = await self._transport.resolve_site_packages_path(
            self._venv_path + "/bin/python",
            working_dir=self._transport.working_dir,
        )
        pth_path = site_packages + "/mindor.pth"
        # ``.pth`` entries go on sys.path, so write the parent of the mindor
        # package (``.../src``) rather than the package directory itself.
        pth_entry = posixpath.dirname(self._mindor_source_path)

        # heredoc avoids any quoting pitfalls with paths that contain spaces.
        command = (
            f"cat > {shlex.quote(pth_path)} <<'MINDOR_PTH_EOF'\n"
            f"{pth_entry}\n"
            f"MINDOR_PTH_EOF"
        )

        logging.info("virtualenv: installing mindor source via %s -> %s", pth_path, pth_entry)

        await self._run_remote_command(command)

    async def install_requirements(self, extra_requirements: Iterable[str] = ()) -> None:
        """Pip install mindor's own runtime requirements (shipped alongside
        the remote source tree) plus any ``extra_requirements`` provided by
        the caller. Each extra path is an absolute path on the remote or a
        path relative to the SSH working_dir; missing files are skipped."""
        venv_python = self._venv_path + "/bin/python"
        venv_pip = self._venv_path + "/bin/pip"
        requirements = [ self._mindor_requirements_path(), *extra_requirements ]

        commands: List[str] = [
            # Prefer uv on the remote too: --link-mode=hardlink reuses wheels
            # across venvs on the same filesystem, matching the local path.
            "if command -v uv >/dev/null 2>&1; then "
            f"INSTALL={shlex.quote('uv pip install --python ' + venv_python + ' --link-mode=hardlink')}; "
            "else "
            f"INSTALL={shlex.quote(venv_pip + ' install --disable-pip-version-check')}; "
            "fi"
        ]

        for path in requirements:
            commands.append(
                f"if [ -f {shlex.quote(path)} ]; then "
                f"$INSTALL -r {shlex.quote(path)}; "
                f"fi"
            )

        logging.info("virtualenv: installing remote requirements on %s...", self._transport.host)

        await self._run_remote_command(" && ".join(commands))

    async def start(self, env: Optional[Dict[str, str]] = None) -> SshExecChannel:
        """Launch the worker via the venv's python over an SSH exec channel."""
        venv_python = self._venv_path + "/bin/python"
        commands: List[str] = []

        if self._transport.working_dir:
            commands.append(f"cd {shlex.quote(self._transport.working_dir)}")

        env = { **(self.config.env or {}), **(env or {}) }
        env_prefix = "".join(f"{name}={shlex.quote(str(value))} " for name, value in env.items())
        commands.append(
            f"{env_prefix}exec {shlex.quote(venv_python)} -m {shlex.quote(self.worker_module)}"
        )

        logging.info("virtualenv: launching remote worker on %s...", self._transport.host)

        self._channel = await self._transport.open_exec_channel(" && ".join(commands))

        return self._channel

    async def stop(self) -> None:
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass

            self._channel = None

        await self._transport.close()

    def _resolve_venv_path(self) -> str:
        """Resolve the remote-side venv directory, mirroring the local
        default (``{cwd}/.runtime/components/{worker_id}/venv``) but anchored
        at the SSH transport's ``working_dir``."""
        if self.config.path:
            return self.config.path

        working_dir = self._transport.working_dir

        if working_dir:
            return f"{working_dir.rstrip('/')}/.runtime/components/{self.worker_id}/venv"

        return f".runtime/components/{self.worker_id}/venv"

    def _mindor_requirements_path(self) -> str:
        return self._mindor_source_path + "/core/runtime/bootstrap/requirements.txt"

    async def _run_remote_command(self, command: str) -> None:
        """Run ``command`` on the remote host via a one-shot exec channel
        and wait for exit. Raises ``RuntimeError`` on non-zero exit."""
        if self._transport.working_dir:
            command = f"cd {shlex.quote(self._transport.working_dir)} && {command}"

        channel = await self._transport.open_exec_channel(command)

        try:
            # Drain the channel to EOF so we see the full exit status.
            while True:
                data = await channel.recv()

                if data is None:
                    break
        finally:
            channel.close()
