from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable, Optional

class CommonShell(ABC):
    """Builds remote shell commands for provisioning Python workloads on
    a remote host.

    One concrete subclass per supported login shell on the remote host.
    Callers probe the remote platform during their ``establish()``-style
    verb and pick the right instance (see runtime `process.remote` and
    `virtualenv.remote` for consumers). Each method returns a
    self-contained command string ready to be fed to the SSH transport.

    Methods come in two groups:

    - **Process-level** (``launch_module_command``, ``pyenv_python_path``)
      used by both the process and virtualenv remote runtimes.
    - **Venv-level** (``venv_python_path``, ``create_venv_command``,
      ``write_pth_command``, ``install_requirements_command``) used
      only by the virtualenv remote runtime. They live on the base
      class to keep the dialect selection trivial — callers just do
      not invoke them when they do not apply.
    """

    @property
    @abstractmethod
    def dialect(self) -> str:
        """Short identifier of the shell dialect this instance produces
        (e.g. ``"posix"``, ``"windows"``). Suitable for log lines and
        diagnostics; not for runtime dispatch — use ``isinstance`` for
        that."""

    @abstractmethod
    def launch_module_command(
        self,
        python: str,
        module: str,
        env: Dict[str, str],
        working_dir: Optional[str],
    ) -> str:
        """Launch ``python -m <module>`` under ``working_dir`` (optional)
        with ``env`` set in the subprocess."""

    @abstractmethod
    def create_venv_command(self, python: str, venv_path: str) -> str:
        """Idempotent command: skip if the venv already has a python,
        otherwise run ``<python> -m venv <venv_path>``."""

    @abstractmethod
    def write_pth_command(self, pth_path: str, entry: str) -> str:
        """Write a single-line ``.pth`` file containing ``entry``."""

    @abstractmethod
    def install_requirements_command(
        self,
        venv_path: str,
        requirements: Iterable[str],
    ) -> str:
        """Install the given requirement files into the venv, preferring
        ``uv`` on PATH when available and falling back to the venv's pip."""

    @abstractmethod
    def pyenv_python_path(self, pyenv_root: str, version: str) -> str:
        """Absolute path to the python binary pyenv manages for ``version``."""

    @abstractmethod
    def venv_python_path(self, venv_path: str) -> str:
        """Absolute path to the python binary inside a venv at ``venv_path``."""
