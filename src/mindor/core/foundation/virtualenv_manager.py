from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver
from mindor.core.foundation.ipc_messages import IpcMessage, IpcMessageType
from mindor.core.logger import logging
from mindor.core.utils.locks import FileLock
from mindor.core.utils.subprocess import SubprocessPipeChannel
import mindor, mindor.version
import asyncio, os, shutil, subprocess, time, ulid, venv

_PACKAGE_IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc")

@dataclass
class VirtualEnvWorkerParams:
    """
    Parameters for virtualenv worker runtime configuration.
    Used by foundation layer to configure worker execution environment.
    """
    driver: VirtualEnvDriver = VirtualEnvDriver.PYTHON
    python: Optional[str] = None
    path: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    start_timeout: float = 60.0  # seconds
    stop_timeout: float = 30.0   # seconds

class VirtualEnvRuntimeManager:
    """Generic manager that creates a venv, injects mindor, and runs a worker subprocess."""

    # Subclasses must set this to the module that should be launched with `python -m`.
    _worker_module: str = ""

    def __init__(self, worker_id: str, worker_params: VirtualEnvWorkerParams = None):
        self.worker_id = worker_id
        self.worker_params = worker_params or VirtualEnvWorkerParams()

        self._venv_path: Path = self._resolve_venv_path()
        self._subprocess: Optional[subprocess.Popen] = None
        self._channel: Optional[SubprocessPipeChannel] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._response_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()

        await self._loop.run_in_executor(None, self._ensure_venv)
        await self._loop.run_in_executor(None, self._install_dependencies)

        request_r,  request_w  = os.pipe()
        response_r, response_w = os.pipe()

        try:
            self._subprocess = subprocess.Popen(
                [str(self._venv_python()), "-m", self._worker_module],
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

        self._channel.send({ "type": "init", "payload": self._build_init_payload() })

        await self._wait_for_ready()

        self._response_task = asyncio.create_task(self._handle_responses())

    async def stop(self) -> None:
        if self._channel is not None:
            try:
                stop_message = IpcMessage(type=IpcMessageType.STOP, request_id=ulid.ulid())
                self._channel.send(stop_message.to_params())
            except Exception:
                pass

        if self._subprocess is not None:
            try:
                await self._loop.run_in_executor(
                    None,
                    lambda: self._subprocess.wait(timeout=self.worker_params.stop_timeout),
                )
            except subprocess.TimeoutExpired:
                self._subprocess.terminate()
                try:
                    self._subprocess.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._subprocess.kill()

        if self._response_task is not None:
            self._response_task.cancel()

        if self._channel is not None:
            self._channel.close()

    async def execute(self, payload: Dict[str, Any]) -> Any:
        if self._channel is None:
            raise RuntimeError("Virtualenv worker is not started")

        request_id = ulid.ulid()
        message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id=request_id,
            payload=payload
        )

        future: asyncio.Future = self._loop.create_future()
        self._pending_requests[request_id] = future
        self._channel.send(message.to_params())

        try:
            return await future
        finally:
            self._pending_requests.pop(request_id, None)

    def _build_init_payload(self) -> Dict[str, Any]:
        """Return the payload sent as the first IPC message after worker spawn."""
        return {}

    async def _handle_responses(self) -> None:
        try:
            while True:
                raw = await self._loop.run_in_executor(None, self._channel.recv)
                if raw is None:
                    break

                message = IpcMessage(
                    type=raw.get("type"),
                    request_id=raw.get("request_id"),
                    payload=raw.get("payload"),
                )

                if not message.request_id:
                    continue

                future = self._pending_requests.get(message.request_id)
                if future is None or future.done():
                    continue

                if message.type == IpcMessageType.RESULT or message.type == IpcMessageType.RESULT.value:
                    future.set_result((message.payload or {}).get("output"))
                elif message.type == IpcMessageType.ERROR or message.type == IpcMessageType.ERROR.value:
                    error = (message.payload or {}).get("error", "Unknown error")
                    future.set_exception(Exception(error))
        except asyncio.CancelledError:
            pass

    async def _wait_for_ready(self) -> None:
        """Wait for subprocess to be ready"""
        timeout = self.worker_params.start_timeout
        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            raw = await self._loop.run_in_executor(None, self._channel.recv)
            if raw is None:
                rc = self._subprocess.poll() if self._subprocess else None
                raise RuntimeError(f"Virtualenv worker '{self.worker_id}' exited before becoming ready (rc={rc})")

            message_type = raw.get("type")
            payload = raw.get("payload") or {}

            if message_type in (IpcMessageType.ERROR, IpcMessageType.ERROR.value):
                error = payload.get("error", "Unknown error") if payload else "Unknown error"
                raise RuntimeError(f"Virtualenv worker '{self.worker_id}' failed to start: {error}")

            if message_type in (IpcMessageType.STATUS, IpcMessageType.STATUS.value) and payload.get("status") == "ready":
                return

        raise TimeoutError(f"Virtualenv worker '{self.worker_id}' did not start within {timeout}s")

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
                    "VirtualEnvWorkerParams.python must be set when driver is 'pyenv'."
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
        runtime_requirements_path = Path(str(files("mindor.core.runtime.base") / "requirements.txt"))
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
