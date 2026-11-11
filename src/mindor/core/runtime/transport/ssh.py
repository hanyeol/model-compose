from __future__ import annotations

from typing import Optional, Dict, Union
from mindor.dsl.schema.runtime.remote import SshRemoteTransportConfig
from mindor.core.utils.transport.ssh_client import (
    SshClient,
    SshConnectionParams,
    SshKeyfileAuthParams,
    SshPasswordAuthParams,
)
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from mindor.core.runtime.shell import CommonShell, PosixShell, WindowsShell
import asyncio, re, socket, uuid

class SshRuntimeTransport:
    """Owns one SSH connection used by a remote-capable runtime manager.

    Lifecycle:
        transport = SshRuntimeTransport(config.remote)
        await transport.connect()
        channel = await transport.open_exec_channel(cmd, env=...)
        ...
        await transport.close()
    """
    def __init__(self, config: SshRemoteTransportConfig):
        self.config: SshRemoteTransportConfig = config

        self._client: Optional[SshClient] = SshClient(self._build_connection_params(config))
        self._working_dir: Optional[str] = None

    @property
    def host(self) -> str:
        return self.config.host

    @property
    def working_dir(self) -> Optional[str]:
        return self._working_dir

    @property
    def client(self) -> SshClient:
        if self._client is None:
            raise RuntimeError("SshRuntimeTransport is closed")

        return self._client

    async def connect(self) -> None:
        await self.client.connect()

        if self.config.working_dir:
            self._working_dir = await self._resolve_working_dir(self.config.working_dir)

    async def resolve_remote_path(self, path: str) -> str:
        """Expand a leading ``~`` and canonicalize ``path`` against the
        remote filesystem.

        Pre-resolution is required because downstream shell helpers wrap
        paths in ``shlex.quote`` / PowerShell single quotes, which suppress
        the remote shell's own tilde expansion — a quoted ``'~/foo'``
        reaches bash literally and gets a ``~`` directory created for it.
        """
        return (await self.evaluate_python_expression(
            "python",
            f"__import__('pathlib').Path({path!r}).expanduser().resolve()",
            working_dir=self.working_dir,
        )).strip()

    async def resolve_remote_shell(self) -> CommonShell:
        """Pick a shell dialect by asking the remote python which OS it is on.

        Probing through python keeps the wire shell-neutral — we do not yet
        know whether the remote login shell is bash or PowerShell.
        """
        system = (await self.evaluate_python_expression(
            "python",
            "__import__('platform').system()",
            working_dir=self.working_dir,
        )).strip()

        if system == "Windows":
            return WindowsShell()

        return PosixShell()

    async def open_exec_channel(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
    ) -> SshExecChannel:
        """Run ``command`` on a fresh exec channel over the shared transport.

        ``env`` goes through SSH's ``env`` request, which OpenSSH silently
        drops for anything not whitelisted in ``AcceptEnv`` — prefix
        ``VAR=value`` inline when the variables must actually land.
        """
        def _open() -> SshExecChannel:
            channel = self.client.transport.open_session()

            if env:
                for name, value in env.items():
                    try:
                        channel.update_environment({ name: value })
                    except Exception:
                        pass

            channel.exec_command(command)

            return SshExecChannel(channel)

        return await asyncio.to_thread(_open)

    async def run_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: float = 10.0,
    ) -> str:
        """Run ``command`` under the user's interactive shell and return its
        stdout with PTY noise stripped.

        The interactive shell is required so ``.bashrc`` / ``$PROFILE``,
        pyenv init, conda hooks etc. are sourced — a plain
        ``exec_command`` would skip them. ``echo`` sentinels delimit the
        real stdout because ``echo`` behaves identically in bash and
        PowerShell.
        """
        sentinel = "MINDOR_" + uuid.uuid4().hex
        wrapped_command = f'echo {sentinel}; {command}; echo {sentinel}'

        # Match the ``echo`` output of ``<sentinel>\n<stdout>\n<sentinel>``
        # and reject the PTY-echoed input line, which has ``;`` wedged
        # against the sentinel instead of a bare newline.
        pattern = re.compile(
            r'(?:^|\r|\n)' + re.escape(sentinel) + r'\r?\n([\s\S]*?)(?:^|\r|\n)' + re.escape(sentinel) + r'\r?\n',
            re.MULTILINE,
        )

        return await self._capture_matched_output(wrapped_command, pattern, working_dir, timeout, command)

    async def evaluate_python_expression(
        self,
        executable: str,
        expression: str,
        working_dir: Optional[str] = None,
        timeout: float = 10.0,
    ) -> str:
        """Evaluate ``expression`` in a remote python and return ``str()``
        of the result.

        The script is base64-wrapped so arbitrary quoting and shell
        metacharacters inside ``expression`` reach python untouched by
        either the host or the remote shell.
        """
        import base64

        sentinel = "MINDOR_" + uuid.uuid4().hex
        script = f'print("{sentinel}" + str({expression}) + "{sentinel}")'
        encoded_script = base64.b64encode(script.encode()).decode()
        command = f'{executable} -c "exec(__import__(\'base64\').b64decode(\'{encoded_script}\').decode())"'

        # Match the python echo of ``<sentinel><path><sentinel>`` and reject
        # the command-line echo, which has ``"`` around the sentinel literal.
        pattern = re.compile(re.escape(sentinel) + r'([^"\r\n]+?)' + re.escape(sentinel))

        return await self._capture_matched_output(command, pattern, working_dir, timeout, expression)

    async def close(self) -> None:
        if self._client is None:
            return

        try:
            await self._client.close()
        finally:
            self._client = None

    async def _resolve_working_dir(self, working_dir: str) -> str:
        """Resolve ``working_dir`` to an absolute path via ``cd; pwd``.

        A bare relative path like ``workdir/foo`` is anchored at the
        remote user's home (``~/workdir/foo``) rather than whatever
        directory the login shell happens to start in — so
        ``~/workdir/foo`` and ``workdir/foo`` resolve identically.

        Cannot go through ``resolve_remote_path`` because that helper
        invokes ``python``, and a remote using ``pyenv local`` scoped to
        the working_dir itself would have no ``python`` on PATH until we
        ``cd`` there — which is what this call is for.
        """
        if not working_dir.startswith(("/", "~")):
            working_dir = f"~/{working_dir}"

        return (await self.run_command(f"cd {working_dir}; pwd")).strip()

    async def _capture_matched_output(
        self,
        command: str,
        pattern: "re.Pattern[str]",
        working_dir: Optional[str],
        timeout: float,
        label: str,
    ) -> str:
        def _run() -> str:
            channel = self.client.transport.open_session()

            # Width must be wide enough to hold our command on a single row:
            # readline / linenoise wrap at the pty's reported column count and
            # inject bare \r bytes mid-line when they do, which corrupts the
            # quoting of our python -c script.
            channel.get_pty(term="dumb", width=4096, height=24)
            channel.invoke_shell()
            channel.settimeout(timeout)

            try:
                if working_dir:
                    channel.sendall(f"cd {working_dir}\n".encode())

                channel.sendall((command + "\n").encode())
                channel.sendall(b"exit\n")

                buffer = bytearray()

                try:
                    while True:
                        chunk = channel.recv(65536)

                        if not chunk:
                            break

                        buffer.extend(chunk)

                        match = pattern.search(buffer.decode(errors="replace"))

                        if match:
                            return match.group(1).strip()
                except socket.timeout:
                    pass

                raise RuntimeError(f"could not capture remote command output: {label}")
            finally:
                try:
                    channel.close()
                except Exception:
                    pass

        return await asyncio.to_thread(_run)

    def _build_connection_params(self, config: SshRemoteTransportConfig) -> SshConnectionParams:
        return SshConnectionParams(
            host=config.host,
            port=config.port,
            auth=self._build_auth_params(config),
            keepalive_interval=int(config.keepalive_interval),
        )

    def _build_auth_params(self, config: SshRemoteTransportConfig) -> Union[SshKeyfileAuthParams, SshPasswordAuthParams]:
        if config.key:
            return SshKeyfileAuthParams(
                username=config.user or "",
                keyfile=config.key,
                passphrase=config.key_passphrase,
            )

        if config.password is not None:
            return SshPasswordAuthParams(
                username=config.user or "",
                password=config.password,
            )

        raise ValueError(
            "SSH remote transport requires either `key` or `password`; "
            "SSH agent / default-key fallback is not supported yet."
        )
