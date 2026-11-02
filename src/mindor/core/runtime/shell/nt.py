from __future__ import annotations

from typing import Dict, Iterable, Optional
from .common import CommonShell
import base64, ntpath

class WindowsShell(CommonShell):
    """PowerShell dialect for Windows hosts. Assumes the remote OpenSSH
    default shell has been set to ``powershell.exe`` or ``pwsh.exe`` —
    the Windows default is ``cmd.exe``, which this class does not
    target."""

    @property
    def dialect(self) -> str:
        return "windows"

    def launch_module_command(
        self,
        python: str,
        module: str,
        env: Dict[str, str],
        working_dir: Optional[str],
    ) -> str:
        commands = []

        if working_dir:
            commands.append(f"Set-Location -LiteralPath {self._quote(working_dir)}")

        for name, value in env.items():
            commands.append(f"$env:{name} = {self._quote(str(value))}")

        # PowerShell's `&` call operator cannot `exec`-replace the shell; the
        # worker runs as a child of the login powershell. SIGINT is still
        # relayed because OpenSSH's shell forwards Ctrl-C.
        commands.append(f"& {self._quote(python)} -m {self._quote(module)}")

        return "; ".join(commands)

    def oneliner_script_command(self, python: str, script: str) -> str:
        script = base64.b64encode(script.encode()).decode()

        # PowerShell: double-quoted strings interpolate, so we build the
        # inner python ``-c`` body with single quotes around the b64 blob.
        return (
            f"& {self._quote(python)} -c "
            f'"exec(__import__(\'base64\').b64decode(\'{script}\').decode())"'
        )

    def create_venv_command(self, python: str, venv_path: str) -> str:
        venv_python = self.venv_python_path(venv_path)

        return (
            f"if (-not (Test-Path -LiteralPath {self._quote(venv_python)})) {{ "
            f"& {self._quote(python)} -m venv {self._quote(venv_path)} "
            f"}}"
        )

    def write_pth_command(self, pth_path: str, entry: str) -> str:
        # Set-Content writes with the configured encoding; -Encoding ascii keeps
        # the file sys.path-compatible on vanilla CPython installs.
        return (
            f"Set-Content -LiteralPath {self._quote(pth_path)} "
            f"-Encoding ascii -Value {self._quote(entry)}"
        )

    def install_requirements_command(
        self,
        venv_path: str,
        requirements: Iterable[str],
    ) -> str:
        venv_python = self.venv_python_path(venv_path)
        venv_pip = ntpath.join(venv_path, "Scripts", "pip.exe")

        commands = [
            "$HasUv = (Get-Command uv -ErrorAction SilentlyContinue) -ne $null",
        ]

        for requirement in requirements:
            requirement = self._quote(requirement)
            uv_cmd = f"& uv pip install --python {self._quote(venv_python)} --link-mode=hardlink -r {requirement}"
            pip_cmd = f"& {self._quote(venv_pip)} install --disable-pip-version-check -r {requirement}"
            commands.append(
                f"if (Test-Path -LiteralPath {requirement}) {{ "
                f"if ($HasUv) {{ {uv_cmd} }} else {{ {pip_cmd} }} "
                f"}}"
            )

        return "; ".join(commands)

    def pyenv_python_path(self, pyenv_root: str, version: str) -> str:
        # pyenv-win layout: {root}\versions\{version}\python.exe
        return ntpath.join(pyenv_root, "versions", version, "python.exe")

    def venv_python_path(self, venv_path: str) -> str:
        return ntpath.join(venv_path, "Scripts", "python.exe")

    def join_path(self, *parts: str) -> str:
        return ntpath.join(*parts)

    @staticmethod
    def _quote(value: str) -> str:
        """Single-quote for PowerShell: wrap in ``'...'`` and double any
        embedded single quote. PowerShell does not interpret escape
        sequences inside single-quoted strings, so paths with ``$`` or
        backticks pass through verbatim."""
        return "'" + value.replace("'", "''") + "'"
