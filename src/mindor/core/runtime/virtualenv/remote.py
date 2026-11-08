from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Dict, Iterable, Optional
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.runtime.ipc_message import IpcMessage, IpcMessageType
from mindor.core.logger import logging
from mindor.dsl.schema.runtime.remote import SshRemoteTransportConfig
from mindor.core.runtime.transport.ssh import SshRuntimeTransport
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from mindor.core.runtime.shell import CommonShell
from ..common import CommonRuntime
import asyncio

class RemoteVirtualEnvRuntime(CommonRuntime):
    """Lifecycle wrapper around a venv-isolated Python worker on a remote host.

    Mirrors ``LocalVirtualEnvRuntime`` for the ``config.remote`` case: owns
    one SSH transport and provisions a venv on the remote filesystem by
    piping shell commands over `exec_command`. The remote host must already
    have an installed copy of ``mindor`` that `import mindor` can find
    through the user's interactive shell — this runtime wires the venv to
    that installation via a ``mindor.pth`` file rather than shipping the
    source over SSH.

    Supports both POSIX (bash/zsh) and PowerShell login shells on the
    remote; the right command dialect is chosen in `establish()` by asking
    the remote python for ``platform.system()``.

    Typical flow:
        runtime = RemoteVirtualEnvRuntime(remote_config, worker_id, worker_module, config)
        await runtime.establish()
        async with runtime.bootstrap_lock():
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
        remote_config: SshRemoteTransportConfig,
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
        self._shell: Optional[CommonShell] = None
        self._executable: Optional[str] = None
        self._venv_path: Optional[str] = None
        self._mindor_source_path: Optional[str] = None

    @property
    def channel(self) -> Optional[SshExecChannel]:
        return self._channel

    async def establish(self) -> None:
        """Open the SSH connection and resolve the pieces downstream verbs
        need: the remote shell dialect, the python executable, the venv
        path, and the remote ``mindor`` source location."""
        await self._transport.connect()

        self._shell = await self._transport.resolve_remote_shell()

        logging.debug("virtualenv: using remote shell dialect %s", self._shell.dialect)

        self._executable = await self._resolve_executable()
        self._venv_path = await self._resolve_venv_path()
        self._mindor_source_path = await self._transport.evaluate_python_expression(
            self._executable,
            "__import__('pathlib').Path(__import__('mindor').__file__).parent",
            working_dir=self._transport.working_dir,
        )

    @asynccontextmanager
    async def bootstrap_lock(self, timeout: float = 300.0):
        """Serialize provisioning across concurrent bootstraps of the same
        remote venv. Mirrors ``LocalVirtualEnvRuntime.bootstrap_lock``:
        all three provisioning verbs (`create_venv`,
        `install_mindor_source`, `install_requirements`) must run inside
        this context so a parallel runner cannot observe a half-built venv.

        A short Python one-liner acts as the lock holder on the remote —
        it takes an exclusive advisory lock on ``{venv}/.mindor.lock``
        (``fcntl.flock`` on POSIX, ``msvcrt.locking`` on Windows), prints
        a ready sentinel, and blocks on stdin. Releasing the lock is just
        closing the SSH channel; the process dies, the fd is closed, and
        the kernel drops the lock. Works whether the venv already exists
        or not — the holder opens the lock file with ``O_CREAT``."""
        lock_path = self._shell.join_path(self._venv_path, ".mindor.lock")
        script = self._build_lock_holder_script(lock_path)
        command = self._shell.oneliner_script_command(self._executable, script)

        logging.debug("virtualenv: acquiring remote bootstrap lock at %s", lock_path)

        channel = await self._transport.open_exec_channel(command)

        try:
            await asyncio.wait_for(self._await_lock_ready(channel), timeout=timeout)
        except Exception:
            channel.close()
            raise

        try:
            yield
        finally:
            channel.close()

    async def create_venv(self) -> None:
        """Run ``<python> -m venv <path>`` on the remote host (idempotent)."""
        command = self._shell.create_venv_command(self._executable, self._venv_path)

        logging.info("virtualenv: creating remote venv at %s:%s...", self._transport.host, self._venv_path)

        await self._run_remote_command(command)

    async def install_mindor_source(self) -> None:
        """Write a ``mindor.pth`` file into the remote venv's site-packages
        pointing at the ``mindor`` package directory resolved during
        `establish()`.

        This is the editable-install path on the remote: whatever ``import
        mindor`` resolves to on the remote user's shell is what the venv
        picks up, so there is no byte transfer from host to remote.
        """
        venv_python = self._shell.venv_python_path(self._venv_path)

        site_packages = await self._transport.evaluate_python_expression(
            venv_python,
            "__import__('sysconfig').get_paths()['purelib']",
            working_dir=self._transport.working_dir,
        )

        # ``.pth`` entries go on sys.path, so write the parent of the mindor
        # package (``.../src``) rather than the package directory itself.
        # Both parent lookups use pathlib on the remote so the slash dialect
        # follows the remote filesystem, not the host's.
        # repr() emits a Python literal with backslashes escaped — safe to
        # embed in the remote python expression even on Windows paths.
        mindor_source_root = await self._transport.evaluate_python_expression(
            self._executable,
            f"__import__('pathlib').Path({self._mindor_source_path!r}).parent",
            working_dir=self._transport.working_dir,
        )

        pth_path = self._shell.join_path(site_packages, "mindor.pth")

        command = self._shell.write_pth_command(pth_path, mindor_source_root)

        logging.info("virtualenv: installing mindor source via %s -> %s", pth_path, mindor_source_root)

        await self._run_remote_command(command)

    async def install_requirements(self, extra_requirements: Iterable[str] = ()) -> None:
        """Pip install mindor's own runtime requirements (shipped alongside
        the remote source tree) plus any ``extra_requirements`` provided by
        the caller. Each extra path is an absolute path on the remote or a
        path relative to the SSH working_dir; missing files are skipped."""
        requirements = [ await self._mindor_requirements_path(), *extra_requirements ]

        command = self._shell.install_requirements_command(self._venv_path, requirements)

        logging.info("virtualenv: installing remote requirements on %s...", self._transport.host)

        await self._run_remote_command(command)

    async def start(self, env: Optional[Dict[str, str]] = None) -> SshExecChannel:
        """Launch the worker via the venv's python over an SSH exec channel."""
        env = { **(self.config.env or {}), **(env or {}) }
        command = self._shell.launch_module_command(
            self._shell.venv_python_path(self._venv_path),
            self.worker_module,
            env,
            self._transport.working_dir,
        )

        logging.info("virtualenv: launching remote worker on %s...", self._transport.host)

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

    async def _resolve_executable(self) -> str:
        """Return the absolute path to the python used to create the venv.

        Dispatches to a driver-specific resolver; the resolvers mirror
        ``LocalVirtualEnvRuntime``'s per-driver branches."""
        if self.config.driver == VirtualEnvDriver.PYTHON:
            return await self._resolve_native_python()

        if self.config.driver == VirtualEnvDriver.PYENV:
            return await self._resolve_pyenv_python(self.config.python)

        raise ValueError(f"Unknown virtualenv driver: {self.config.driver}")

    async def _resolve_native_python(self) -> str:
        """Resolve whatever ``python`` the remote user's interactive shell
        exposes (pyenv shim, conda, system — whichever is first on PATH).

        Asks the remote python to print its own ``sys.executable`` so we
        get the absolute binary path, not the shim.
        """
        return await self._transport.evaluate_python_expression(
            "python",
            "__import__('sys').executable",
            working_dir=self._transport.working_dir,
        )

    async def _resolve_pyenv_python(self, version: str) -> str:
        """Mirror of ``LocalVirtualEnvRuntime._resolve_pyenv_python`` on the
        remote: queries pyenv for installed versions and root, then returns
        the absolute path to the pyenv-managed python binary (pyenv on
        POSIX, pyenv-win on Windows).

        pyenv shims rely on the user's shell init, so these probes run under
        the remote interactive shell via ``run_command``.
        """
        working_dir = self._transport.working_dir

        try:
            installed_output = await self._transport.run_command(
                "pyenv versions --bare",
                working_dir=working_dir,
            )
        except RuntimeError as e:
            raise RuntimeError("pyenv command not found on remote. Install pyenv or switch to driver: python.") from e

        installed_versions = [ v.strip() for v in installed_output.splitlines() if v.strip() ]

        if version not in installed_versions:
            raise RuntimeError(
                f"Python version '{version}' is not installed in pyenv on remote. "
                f"Run `pyenv install {version}` on {self._transport.host} first."
            )

        pyenv_root = (await self._transport.run_command(
            "pyenv root",
            working_dir=working_dir,
        )).strip()

        return self._shell.pyenv_python_path(pyenv_root, version)

    async def _resolve_venv_path(self) -> str:
        """Resolve the remote-side venv directory, mirroring the local
        default (``{cwd}/.runtime/components/{worker_id}/venv``) but anchored
        at the SSH transport's ``working_dir``.

        ``config.path`` is resolved on the remote via the transport so
        ``~``, ``..``, and symlinks all canonicalize against the real
        filesystem; a relative path is anchored at ``working_dir`` (already
        absolute at this point) before resolution so the venv lands next
        to the project regardless of the login shell's cwd. Pre-resolving
        is required because downstream ``shlex.quote`` would otherwise send
        ``'~/foo'`` through literally and have bash create a ``~`` directory.

        Uses the remote shell's path join so forward/backslash follows the
        remote filesystem's convention."""
        working_dir = self._transport.working_dir or "."

        if self.config.path:
            if not self._shell.is_absolute_path(self.config.path) and not self.config.path.startswith("~"):
                path = self._shell.join_path(working_dir, self.config.path)
            else:
                path = self.config.path

            return await self._transport.resolve_remote_path(path)

        return self._shell.join_path(working_dir, ".runtime", "components", self.worker_id, "venv")

    async def _mindor_requirements_path(self) -> str:
        """``{mindor_source}/core/runtime/bootstrap/requirements.txt`` with
        the remote's path separators. Resolved on the remote via pathlib to
        avoid host-side slash guessing."""
        return await self._transport.evaluate_python_expression(
            self._executable,
            f"__import__('pathlib').Path({self._mindor_source_path!r}) "
            "/ 'core' / 'runtime' / 'bootstrap' / 'requirements.txt'",
            working_dir=self._transport.working_dir,
        )

    async def _run_remote_command(self, command: str) -> None:
        """Run ``command`` on the remote host via a one-shot exec channel
        and wait for exit. Raises ``RuntimeError`` on non-zero exit."""
        working_dir = self._transport.working_dir

        if working_dir:
            command = f"cd {working_dir}; {command}"

        channel = await self._transport.open_exec_channel(command)

        try:
            # Drain the channel to EOF so we see the full exit status.
            while True:
                data = await channel.recv()

                if data is None:
                    break
        finally:
            channel.close()

    @staticmethod
    def _build_lock_holder_script(lock_path: str) -> str:
        """Script body executed on the remote: acquires an exclusive
        advisory lock on ``lock_path`` using the right OS primitive,
        emits a STATUS IPC message signalling readiness, then blocks
        on stdin so the host can release the lock by closing the exec
        channel. Inlining ``lock_path`` and the pre-built ready
        message with ``repr()`` sidesteps shell quoting entirely —
        the whole script is base64-wrapped by
        ``oneliner_script_command``."""
        ready_message = IpcMessage(
            type=IpcMessageType.STATUS,
            payload={ "status": "lock-ready" }
        )

        return (
            "import os, sys\n"
            f"lock_path = {lock_path!r}\n"
            f"ready_message = {ready_message.serialize()!r}\n"
            "os.makedirs(os.path.dirname(lock_path), exist_ok=True)\n"
            "fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)\n"
            "if sys.platform == 'win32':\n"
            "    import msvcrt\n"
            "    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)\n"
            "else:\n"
            "    import fcntl\n"
            "    fcntl.flock(fd, fcntl.LOCK_EX)\n"
            "sys.stdout.buffer.write(ready_message)\n"
            "sys.stdout.buffer.flush()\n"
            "sys.stdin.read()\n"
        )

    @staticmethod
    async def _await_lock_ready(channel: SshExecChannel) -> None:
        """Wait for the holder's STATUS(lock-ready) IPC message.

        The holder sends a single length-prefixed IPC message after
        acquiring the lock; ``channel.recv()`` reads one complete
        message at a time, so one call is enough."""
        serialized = await channel.recv()

        if serialized is None:
            raise RuntimeError("remote lock holder exited before signalling readiness")

        message = IpcMessage.deserialize(serialized)

        if message.type != IpcMessageType.STATUS or (message.payload or {}).get("status") != "lock-ready":
            raise RuntimeError(f"unexpected IPC frame from remote lock holder: {message.type}")

