from __future__ import annotations

from typing import Dict, Iterable, Optional
from .common import CommonShell
import base64, posixpath, shlex

class PosixShell(CommonShell):
    """bash / sh / zsh. Used when the remote login shell is POSIX."""

    @property
    def dialect(self) -> str:
        return "posix"

    def launch_module_command(
        self,
        python: str,
        module: str,
        env: Dict[str, str],
        working_dir: Optional[str],
    ) -> str:
        commands = []

        if working_dir:
            commands.append(f"cd {shlex.quote(working_dir)}")

        # OpenSSH servers often reject SetEnv for anything not whitelisted in
        # sshd_config, so prefix VAR=value inline. `exec` replaces the shell
        # so signals reach the Python worker directly.
        env_prefix = "".join(f"{name}={shlex.quote(str(value))} " for name, value in env.items())
        commands.append(
            f"{env_prefix}exec {shlex.quote(python)} -m {shlex.quote(module)}"
        )

        return " && ".join(commands)

    def oneliner_script_command(self, python: str, script: str) -> str:
        script = base64.b64encode(script.encode()).decode()

        # `-u` forces unbuffered stdio: SSH exec channels have no pty, so
        # Python's stdout defaults to block-buffering and small sentinel
        # writes (e.g. the lock-ready marker) never reach the host until
        # the script exits.
        return (
            f"{shlex.quote(python)} -u -c "
            f"\"exec(__import__('base64').b64decode('{script}').decode())\""
        )

    def create_venv_command(self, python: str, venv_path: str) -> str:
        venv_python = self.venv_python_path(venv_path)

        return (
            f"test -x {shlex.quote(venv_python)} || "
            f"{shlex.quote(python)} -m venv {shlex.quote(venv_path)}"
        )

    def write_pth_command(self, pth_path: str, entry: str) -> str:
        # heredoc avoids any quoting pitfalls with paths that contain spaces.
        return (
            f"cat > {shlex.quote(pth_path)} <<'MINDOR_PTH_EOF'\n"
            f"{entry}\n"
            f"MINDOR_PTH_EOF"
        )

    def install_requirements_command(
        self,
        venv_path: str,
        requirements: Iterable[str],
    ) -> str:
        venv_python = self.venv_python_path(venv_path)
        venv_pip = posixpath.join(venv_path, "bin", "pip")

        commands = [
            "if command -v uv >/dev/null 2>&1; then "
            f"INSTALL={shlex.quote('uv pip install --python ' + venv_python)}; "
            "else "
            f"INSTALL={shlex.quote(venv_pip + ' install --disable-pip-version-check')}; "
            "fi"
        ]

        for requirement in requirements:
            commands.append(
                f"if [ -f {shlex.quote(requirement)} ]; then "
                f"$INSTALL -r {shlex.quote(requirement)}; "
                f"fi"
            )

        return " && ".join(commands)

    def pyenv_python_path(self, pyenv_root: str, version: str) -> str:
        return posixpath.join(pyenv_root, "versions", version, "bin", "python")

    def venv_python_path(self, venv_path: str) -> str:
        return posixpath.join(venv_path, "bin", "python")

    def join_path(self, *parts: str) -> str:
        return posixpath.join(*parts)

    def is_absolute_path(self, path: str) -> bool:
        return posixpath.isabs(path)
