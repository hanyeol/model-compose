from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver
from mindor.core.logger import logging
from mindor.core.utils.locks import FileLock
from mindor.core.utils.transport.subprocess_pipe import SubprocessPipeChannel
from mindor.core.runtime.base.ipc_manager import IpcRuntimeManager
from mindor.core.runtime.base.ipc_message import IpcMessage, IpcMessageType
from mindor.core.runtime.base.ipc_worker import IpcRuntimeWorker
from importlib.resources import files
from pathlib import Path
import mindor, mindor.version
import asyncio, os, shutil, subprocess, venv

_PACKAGE_IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc")


class VirtualEnvRuntimeWorker(IpcRuntimeWorker):
    """
    Base class for workers launched in a separate Python interpreter (virtualenv).

    Communicates with the parent process through a line-framed bytes channel
    (`SubprocessPipeChannel`). Serialized IPC messages travel as bytes.
    """

    def __init__(self, worker_id: str, channel: SubprocessPipeChannel):
        super().__init__(worker_id)
        self.channel = channel

    async def _send_message(self, message: bytes) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.channel.recv)

    def _close_transport(self) -> None:
        self.channel.close()


@dataclass
class VirtualEnvRuntimeManagerParams:
    """
    Parameters for the virtualenv runtime manager.
    Used to configure venv creation and how the worker subprocess is spawned and managed.
    """
    driver: VirtualEnvDriver = VirtualEnvDriver.PYTHON
    python: Optional[str] = None
    path: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    start_timeout: float = 60.0  # seconds
    stop_timeout: float = 30.0   # seconds


class VirtualEnvRuntimeManager(IpcRuntimeManager):
    """Generic manager that creates a venv, injects mindor, and runs a worker subprocess."""

    def __init__(
        self,
        worker_id: str,
        worker_module: str,
        worker_params: VirtualEnvRuntimeManagerParams = None
    ):
        super().__init__(worker_id)

        self.worker_module = worker_module
        self.worker_params = worker_params or VirtualEnvRuntimeManagerParams()

        self._venv_path: Path = self._resolve_venv_path()
        self._subprocess: Optional[subprocess.Popen] = None
        self._channel: Optional[SubprocessPipeChannel] = None

        self._start_timeout = self.worker_params.start_timeout
        self._stop_timeout = self.worker_params.stop_timeout

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()

        await self._loop.run_in_executor(None, self._ensure_venv)
        await self._loop.run_in_executor(None, self._install_dependencies)

        request_r,  request_w  = os.pipe()
        response_r, response_w = os.pipe()

        try:
            self._subprocess = subprocess.Popen(
                [ str(self._venv_python()), "-m", self.worker_module ],
                pass_fds=(request_r, response_w),
                env=self._build_environment(request_r, response_w),
                stdin=subprocess.DEVNULL,
                stdout=None,
                stderr=None,
                close_fds=True,
            )
        finally:
            # The child has duplicated the read end of the request pipe and the write end
            # of the response pipe; close the parent-side copies so only the child holds them.
            os.close(request_r)
            os.close(response_w)

        # Parent uses: read responses on response_r, write requests on request_w.
        self._channel = SubprocessPipeChannel(request_fd=response_r, response_fd=request_w)

        await self._send_message(IpcMessage(
            type=IpcMessageType.START,
            payload=self._build_init_payload(),
        ).serialize())

        await self._wait_for_ready()

        self._response_task = asyncio.create_task(self._handle_responses())

    async def stop(self) -> None:
        if self._channel is not None:
            await self._send_stop_message()

        if self._subprocess is not None:
            try:
                await self._loop.run_in_executor(
                    None,
                    lambda: self._subprocess.wait(timeout=self._stop_timeout),
                )
            except subprocess.TimeoutExpired:
                self._subprocess.terminate()
                try:
                    self._subprocess.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._subprocess.kill()

        # Child exit closes its write-end of the pipe, so the executor thread
        # parked in self._channel.recv() (readline) wakes with EOF → None.
        # Await the task so it finishes naturally before closing the channel,
        # otherwise loop.shutdown_default_executor() hangs on the parked thread.
        if self._response_task is not None:
            try:
                await self._response_task
            except asyncio.CancelledError:
                pass

        if self._channel is not None:
            self._channel.close()

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._channel.recv)

    def _build_init_payload(self) -> Dict[str, Any]:
        """Return the payload sent as the first IPC message after worker spawn."""
        return {}

    def _build_environment(self, request_fd: int, response_fd: int) -> Dict[str, str]:
        env = dict(os.environ)
        env.update(self.worker_params.env or {})
        env.update({
            "PYTHONUNBUFFERED":        "1",
            "MINDOR_VENV_REQUEST_FD":  str(request_fd),
            "MINDOR_VENV_RESPONSE_FD": str(response_fd),
        })
        return env

    def _resolve_venv_path(self) -> Path:
        path = self.worker_params.path
        if path:
            return (Path.cwd() / path).resolve()
        return (Path.cwd() / ".runtime" / "components" / self.worker_id / "venv").resolve()

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
        out = subprocess.check_output(
            [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            text=True,
        ).strip()
        return Path(out)

    def _ensure_venv(self) -> None:
        if self._venv_path.exists() and self._venv_python().exists():
            return

        self._venv_path.parent.mkdir(parents=True, exist_ok=True)

        if self.worker_params.driver == VirtualEnvDriver.PYTHON:
            logging.info(f"Creating virtualenv at {self._venv_path} (python driver)")
            builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False)
            builder.create(str(self._venv_path))
            return

        if self.worker_params.driver == VirtualEnvDriver.PYENV:
            version = self.worker_params.python
            if not version:
                raise ValueError(
                    "VirtualEnvRuntimeManagerParams.python must be set when driver is 'pyenv'."
                )

            python_path = self._resolve_pyenv_python(version)
            logging.info(
                f"Creating virtualenv at {self._venv_path} (pyenv driver, python {version})"
            )
            subprocess.run([str(python_path), "-m", "venv", str(self._venv_path)], check=True)
            return

        raise ValueError(f"Unknown virtualenv driver: {self.worker_params.driver}")

    def _resolve_pyenv_python(self, version: str) -> Path:
        try:
            installed = subprocess.check_output([ "pyenv", "versions", "--bare" ], text=True).splitlines()
        except FileNotFoundError as e:
            raise RuntimeError(
                "pyenv command not found. Install pyenv or switch to driver: python."
            ) from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to list pyenv versions: {e}") from e

        if version not in [ v.strip() for v in installed ]:
            raise RuntimeError(
                f"Python version '{version}' is not installed in pyenv. "
                f"Run `pyenv install {version}` first."
            )

        try:
            pyenv_root = subprocess.check_output([ "pyenv", "root" ], text=True).strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to resolve pyenv root: {e}") from e

        python_path = Path(pyenv_root) / "versions" / version / "bin" / "python"
        if not python_path.exists():
            raise RuntimeError(
                f"pyenv reports {version} as installed but {python_path} does not exist."
            )
        return python_path

    def _install_dependencies(self) -> None:
        site_packages = self._venv_site_packages()
        site_packages.mkdir(parents=True, exist_ok=True)
        target_mindor = site_packages / "mindor"
        version_path = target_mindor / ".version"

        host_mindor_root = Path(mindor.__file__).resolve().parent
        runtime_requirements_path = Path(str(files("mindor.core.runtime.bootstrap") / "requirements.txt"))
        user_requirements_path = (Path.cwd() / "requirements.txt").resolve()

        current_version = mindor.version.__version__
        existing_version = version_path.read_text().strip() if version_path.exists() else None
        needs_mindor_copy = existing_version != current_version

        with FileLock(self._venv_path / ".lock"):
            if needs_mindor_copy:
                if target_mindor.exists():
                    shutil.rmtree(target_mindor)

                staging = site_packages / f".mindor.staging.{os.getpid()}"
                if staging.exists():
                    shutil.rmtree(staging)
                shutil.copytree(host_mindor_root, staging, ignore=_PACKAGE_IGNORE_PATTERNS)
                os.replace(staging, target_mindor)

                version_path.write_text(current_version)

            # pip skips already-satisfied requirements, so always run cheaply
            pip = str(self._venv_pip())
            subprocess.run(
                [pip, "install", "--disable-pip-version-check", "-r", str(runtime_requirements_path)],
                check=True,
            )
            if user_requirements_path.exists():
                subprocess.run(
                    [pip, "install", "--disable-pip-version-check", "-r", str(user_requirements_path)],
                    check=True,
                )
