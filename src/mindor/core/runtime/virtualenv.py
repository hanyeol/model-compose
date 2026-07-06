from __future__ import annotations

from typing import Dict, Optional, Tuple
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.logger import logging
from mindor.core.utils.locks import FileLock
from importlib.resources import files
from pathlib import Path
import mindor, mindor.version
import asyncio, os, shutil, subprocess, venv

_PACKAGE_IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc")

class VirtualEnvRuntime:
    """Lifecycle wrapper around a venv-isolated Python worker subprocess.

    Pure lifecycle:
    - Bootstraps a venv (driver: python | pyenv), copies the host `mindor` package
      into it, installs runtime + user requirements.
    - Spawns the interpreter on `python -m <worker_module>` with caller-supplied
      `pass_fds` and `env` overrides — the caller is responsible for creating IPC
      pipes (or any other transport) and threading their fds through.
    - On stop, attempts graceful exit then escalates to terminate / kill.

    Knows nothing about IPC protocols, codecs, or channels.
    """
    def __init__(
        self,
        worker_id: str,
        worker_module: str,
        config: VirtualEnvRuntimeConfig,
        verbose: bool = False,
    ):
        self.worker_id = worker_id
        self.worker_module = worker_module
        self.config = config
        self.verbose = verbose

        self._venv_path: Path = self._resolve_venv_path()
        self._subprocess: Optional[subprocess.Popen] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(
        self,
        *,
        pass_fds: Tuple[int, ...] = (),
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """Bootstrap the venv (idempotent) and spawn the worker subprocess.

        `pass_fds` and `env` let the caller propagate transport handles
        (e.g., pipe read/write fds) without this lifecycle class knowing about them.
        """
        self._loop = asyncio.get_event_loop()

        await self._loop.run_in_executor(None, self._ensure_venv)
        await self._loop.run_in_executor(None, self._install_dependencies)

        self._subprocess = subprocess.Popen(
            [ str(self._venv_python()), "-m", self.worker_module ],
            pass_fds=pass_fds,
            env=self._build_environment(env),
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            close_fds=True,
        )

    async def stop(self) -> None:
        if self._subprocess:
            stop_timeout = parse_duration(self.config.stop_timeout)
            try:
                await self._loop.run_in_executor(
                    None,
                    lambda: self._subprocess.wait(timeout=stop_timeout),
                )
            except subprocess.TimeoutExpired:
                self._subprocess.terminate()
                try:
                    self._subprocess.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._subprocess.kill()
            self._subprocess = None

    @property
    def is_alive(self) -> bool:
        return self._subprocess is not None and self._subprocess.poll() is None

    @property
    def subprocess(self) -> Optional[subprocess.Popen]:
        return self._subprocess

    def _build_environment(self, overrides: Optional[Dict[str, str]]) -> Dict[str, str]:
        env = dict(os.environ)
        env.update(self.config.env or {})
        env["PYTHONUNBUFFERED"] = "1"
        if overrides:
            env.update(overrides)
        return env

    def _resolve_venv_path(self) -> Path:
        path = self.config.path
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

        if self.config.driver == VirtualEnvDriver.PYTHON:
            logging.info(f"Creating virtualenv at {self._venv_path} (python driver)")
            builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False)
            builder.create(str(self._venv_path))
            return

        if self.config.driver == VirtualEnvDriver.PYENV:
            version = self.config.python
            if not version:
                raise ValueError(
                    "VirtualEnvRuntimeConfig.python must be set when driver is 'pyenv'."
                )

            python_path = self._resolve_pyenv_python(version)
            logging.info(
                f"Creating virtualenv at {self._venv_path} (pyenv driver, python {version})"
            )
            subprocess.run([str(python_path), "-m", "venv", str(self._venv_path)], check=True)
            return

        raise ValueError(f"Unknown virtualenv driver: {self.config.driver}")

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
                [ pip, "install", "--disable-pip-version-check", "-r", str(runtime_requirements_path) ],
                check=True,
            )
            if user_requirements_path.exists():
                subprocess.run(
                    [ pip, "install", "--disable-pip-version-check", "-r", str(user_requirements_path) ],
                    check=True,
                )
