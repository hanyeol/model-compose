from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from contextlib import asynccontextmanager
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver
from mindor.core.foundation.package import mindor as mindor_package
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
from mindor.core.runtime.transport.ssh import SshRuntimeTransport, SshBasedRemoteTransportConfig
from mindor.core.utils.archive import archive_to_directory, skip_python_artifacts
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from mindor.core.utils.locks import FileLock
from .common import CommonRuntime
from pathlib import Path
import asyncio, os, posixpath, shlex, shutil, subprocess, venv

# Host env vars excluded from the worker subprocess to preserve venv isolation.
# LD_LIBRARY_PATH/LD_PRELOAD/CUDA_* let the host's system CUDA shadow the venv's
# bundled CUDA libs (e.g. torch cu128 wheel vs system CUDA 12.9), causing subtle
# runtime errors like cuBLAS INVALID_VALUE. PYTHONPATH/PYTHONHOME leak the host
# site-packages into the venv interpreter. Users can re-add anything they need
# via `runtime.env` — that dict is applied after this strip.
_EXCLUDED_HOST_ENV_VARS = frozenset({
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "CUDA_HOME",
    "CUDA_PATH",
    "CUDA_ROOT",
    "PYTHONPATH",
    "PYTHONHOME",
})

class LocalVirtualEnvRuntime(CommonRuntime):
    """Lifecycle wrapper around a venv-isolated Python worker subprocess.

    Owns a single venv on disk and exposes high-level provisioning verbs
    (`create_venv`, `install_mindor_source`, `install_requirements`) and process
    lifecycle (`start`/`stop`) for its parent manager to orchestrate.
    Encapsulates every venv-internal detail — site-packages discovery,
    `.pth` layout, pip vs uv, platform-specific binaries — so the manager
    stays runtime-agnostic.
    """
    config: VirtualEnvRuntimeConfig

    def __init__(
        self,
        worker_id: str,
        worker_module: str,
        config: VirtualEnvRuntimeConfig,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self.worker_id = worker_id
        self.worker_module = worker_module

        self._stop_timeout = parse_time(config.stop_timeout) if config.stop_timeout is not None else None

        self._venv_path: Path = self._resolve_venv_path()
        self._mindor_source_path: Path = mindor_package.get_root_path()
        self._subprocess: Optional[subprocess.Popen] = None

    @property
    def is_alive(self) -> bool:
        return self._subprocess is not None and self._subprocess.poll() is None

    @property
    def subprocess(self) -> Optional[subprocess.Popen]:
        return self._subprocess

    @asynccontextmanager
    async def bootstrap_lock(self):
        """Serialize provisioning across concurrent bootstraps of the same
        venv path. All three provisioning verbs (`create_venv`,
        `install_mindor_source`, `install_requirements`) must be called inside this
        context so a parallel runner cannot observe a half-built venv."""
        self._venv_path.mkdir(parents=True, exist_ok=True)

        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        lock = FileLock(self._venv_path / ".mindor.lock")

        def _acquire() -> None:
            lock.__enter__()

        def _release() -> None:
            lock.__exit__(None, None, None)

        await loop.run_in_executor(None, _acquire)

        try:
            yield
        finally:
            await loop.run_in_executor(None, _release)

    async def create_venv(self) -> None:
        """Create the venv (interpreter + pip) if missing. Idempotent."""
        def _create_venv() -> None:
            if self._venv_python().exists():
                return

            if self.config.driver == VirtualEnvDriver.PYTHON:
                logging.info("virtualenv: creating at %s (python driver)...", self._venv_path)

                builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False)
                builder.create(str(self._venv_path))

                return

            if self.config.driver == VirtualEnvDriver.PYENV:
                logging.info(
                    "virtualenv: creating at %s (pyenv driver, python %s)...",
                    self._venv_path,
                    self.config.python,
                )

                python_path = self._resolve_pyenv_python(self.config.python)
                subprocess.run([ str(python_path), "-m", "venv", str(self._venv_path) ], check=True)

                return

            raise ValueError(f"Unknown virtualenv driver: {self.config.driver}")

        await asyncio.get_event_loop().run_in_executor(None, _create_venv)

    async def install_mindor_source(self) -> None:
        """Mirror the host ``mindor`` package into the venv's site-packages."""
        def _install_mindor_source() -> None:
            site_packages = self._venv_site_packages()
            site_packages.mkdir(parents=True, exist_ok=True)

            venv_mindor_path = site_packages / "mindor"
            venv_pth_path = site_packages / "mindor.pth"

            if self._is_editable_install():
                if venv_mindor_path.exists():
                    shutil.rmtree(venv_mindor_path)

                venv_pth_path.write_text(f"{self._mindor_source_path.parent}\n")

                return

            if venv_pth_path.exists():
                venv_pth_path.unlink()

            venv_version_path = venv_mindor_path / ".version"
            host_mindor_version = mindor_package.get_version()
            venv_mindor_version = venv_version_path.read_text().strip() if venv_version_path.exists() else None

            if venv_mindor_version != host_mindor_version:
                if venv_mindor_path.exists():
                    shutil.rmtree(venv_mindor_path)

                # Stage via archive_to_directory: it uses `tempfile.mkdtemp` under
                # `site_packages` (same filesystem, so the follow-up `os.replace`
                # is atomic) and auto-cleans the temp dir on exit, even if the
                # replace raises.
                with archive_to_directory(
                    dirs={"mindor": self._mindor_source_path},
                    filter=skip_python_artifacts,
                    root=site_packages,
                ) as staging_root:
                    os.replace(staging_root / "mindor", venv_mindor_path)

                venv_version_path.write_text(host_mindor_version)

        await asyncio.get_event_loop().run_in_executor(None, _install_mindor_source)

    async def install_requirements(self, extra_requirements: Iterable[Path] = ()) -> None:
        """Pip install mindor's own runtime requirements plus any
        ``extra_requirements`` provided by the caller. Missing files are
        skipped silently."""
        requirements = [ mindor_package.get_requirements_path(), *extra_requirements ]

        def _install_requirements() -> None:
            # Prefer uv when available: `--link-mode=hardlink` shares wheel
            # bytes across venvs on the same filesystem (torch/CUDA installs
            # cost ~one copy total), and falls back to copy on cross-fs targets.
            uv_path = shutil.which("uv")

            if uv_path:
                command = [ uv_path, "pip", "install", "--python", str(self._venv_python()), "--link-mode=hardlink" ]
            else:
                command = [ str(self._venv_pip()), "install", "--disable-pip-version-check" ]

            for requirements_path in requirements:
                if not requirements_path.exists():
                    continue

                subprocess.run(command + [ "-r", str(requirements_path) ], check=True)

        await asyncio.get_event_loop().run_in_executor(None, _install_requirements)

    async def start(
        self,
        *,
        request_fd: int,
        response_fd: int,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """Spawn the worker subprocess. Assumes bootstrap verbs have already run.

        `request_fd` is the fd the child should read requests from; `response_fd` is
        the fd the child should write responses to. The platform-specific inheritance
        mechanism (POSIX `pass_fds` vs. Windows handle list via `STARTUPINFO`) is
        hidden here so the manager stays platform-agnostic. The MINDOR_VENV_*
        environment variables that the worker's `main()` reads are injected here too.
        """
        worker_env = self._build_venv_environment(env)

        if os.name == "nt":
            self._subprocess = self._spawn_windows(request_fd, response_fd, worker_env)
        else:
            self._subprocess = self._spawn_posix(request_fd, response_fd, worker_env)

    async def stop(self) -> None:
        if self._subprocess:
            try:
                await asyncio.get_event_loop().run_in_executor(None, lambda: self._subprocess.wait(timeout=self._stop_timeout))
            except subprocess.TimeoutExpired:
                self._subprocess.terminate()

                try:
                    self._subprocess.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._subprocess.kill()

            self._subprocess = None

    def _resolve_pyenv_python(self, version: str) -> Path:
        try:
            installed_versions = subprocess.check_output([ "pyenv", "versions", "--bare" ], text=True).splitlines()
        except FileNotFoundError as e:
            raise RuntimeError("pyenv command not found. Install pyenv or switch to driver: python.") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to list pyenv versions: {e}") from e

        if version not in [ version.strip() for version in installed_versions ]:
            raise RuntimeError(f"Python version '{version}' is not installed in pyenv. Run `pyenv install {version}` first.")

        try:
            pyenv_root = subprocess.check_output([ "pyenv", "root" ], text=True).strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to resolve pyenv root: {e}") from e

        python_path = Path(pyenv_root) / "versions" / version / "bin" / "python"

        if not python_path.exists():
            raise RuntimeError(f"pyenv reports {version} as installed but {python_path} does not exist.")

        return python_path

    def _resolve_venv_path(self) -> Path:
        if self.config.path:
            return (Path.cwd() / self.config.path).resolve()

        return (Path.cwd() / ".runtime" / "components" / self.worker_id / "venv").resolve()

    def _build_venv_environment(self, overrides: Optional[Dict[str, str]]) -> Dict[str, str]:
        env = { key: value for key, value in os.environ.items() if key not in _EXCLUDED_HOST_ENV_VARS }

        env.update(self.config.env or {})

        env["PATH"] = str(self._venv_bin()) + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(self._venv_path)
        env["PYTHONUNBUFFERED"] = "1"

        if overrides:
            env.update(overrides)

        return env

    def _venv_python(self) -> Path:
        if os.name == "nt":  # Windows
            return self._venv_path / "Scripts" / "python.exe"

        return self._venv_path / "bin" / "python"

    def _venv_pip(self) -> Path:
        if os.name == "nt":
            return self._venv_path / "Scripts" / "pip.exe"

        return self._venv_path / "bin" / "pip"

    def _venv_site_packages(self) -> Path:
        # Resolve site-packages by asking the venv's python directly. The only reliable
        # way to handle platform/python-version differences.
        python = self._venv_python()
        output = subprocess.check_output(
            [ str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])" ],
            text=True,
        ).strip()

        return Path(output)

    def _venv_bin(self) -> Path:
        if os.name == "nt":  # Windows
            return self._venv_path / "Scripts"

        return self._venv_path / "bin"

    def _spawn_posix(self, request_fd: int, response_fd: int, env: Dict[str, str]) -> subprocess.Popen:
        env["MINDOR_VENV_REQUEST_FD"]  = str(request_fd)
        env["MINDOR_VENV_RESPONSE_FD"] = str(response_fd)

        return subprocess.Popen(
            [ str(self._venv_python()), "-m", self.worker_module ],
            pass_fds=(request_fd, response_fd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            close_fds=True,
        )

    def _spawn_windows(self, request_fd: int, response_fd: int, env: Dict[str, str]) -> subprocess.Popen:
        # Windows doesn't support `pass_fds`; use STARTUPINFO.lpAttributeList's
        # handle_list to restrict inherited handles to just our pipe ends. The
        # worker's main() reads the handle values via MINDOR_VENV_*_HANDLE and
        # converts them back to fds with msvcrt.open_osfhandle.
        #
        # Trade-off: Popen requires close_fds=False when handle_list is set, so
        # other inheritable handles the parent currently owns may leak to the
        # child. os.pipe() returns non-inheritable fds on Python 3.4+, so our own
        # pipe ends aren't accidentally duplicated; we mark only the two we hand
        # over as inheritable right before spawn.
        import msvcrt

        os.set_inheritable(request_fd, True)
        os.set_inheritable(response_fd, True)

        request_handle  = msvcrt.get_osfhandle(request_fd)
        response_handle = msvcrt.get_osfhandle(response_fd)

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.lpAttributeList = { "handle_list": [ request_handle, response_handle ] }

        env["MINDOR_VENV_REQUEST_HANDLE"]  = str(request_handle)
        env["MINDOR_VENV_RESPONSE_HANDLE"] = str(response_handle)

        return subprocess.Popen(
            [ str(self._venv_python()), "-m", self.worker_module ],
            startupinfo=startupinfo,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            close_fds=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

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
