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

    @property
    def host(self) -> str:
        return self.config.host

    @property
    def working_dir(self) -> Optional[str]:
        return self.config.working_dir

    @property
    def client(self) -> SshClient:
        if self._client is None:
            raise RuntimeError("SshRuntimeTransport is closed")

        return self._client

    async def connect(self) -> None:
        await self.client.connect()

    async def close(self) -> None:
        if self._client is None:
            return

        try:
            await self._client.close()
        finally:
            self._client = None

    async def resolve_remote_shell(self) -> CommonShell:
        """Probe the remote login shell by asking python what OS it is on.

        Running ``python -c "import platform; print(platform.system())"``
        bypasses the host shell dialect entirely — the probe wire is the
        same bash/powershell-compatible ``echo``-wrapped sentinel pattern
        the transport uses everywhere else.
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
        """Open a new exec channel on the shared transport and run ``command``.

        Each call returns an independent channel — the underlying SSH
        connection is multiplexed, so several channels can run in parallel
        over the same TCP session.

        ``env`` is applied via SSH's ``env`` request; servers that do not
        accept the requested variables silently ignore them, so prefer
        prefixing ``VAR=value`` in the command string when the variables
        are required.
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
        stdout, with the surrounding shell/pty noise stripped.

        The command's own stdout is wrapped between a pair of sentinels that
        we match in the pty transcript; multi-line output is preserved. The
        interactive shell is used so pyenv init, conda hooks, ``.bashrc``
        / ``$PROFILE`` etc. are applied — a plain non-interactive
        ``exec_command`` would skip them.

        ``echo`` is used for sentinel printing because it works verbatim in
        both bash and PowerShell (PowerShell aliases ``echo`` to
        ``Write-Output``). Trailing newlines are tolerated by the pattern.
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
        """Evaluate ``expression`` in a remote python running under the
        user's interactive shell, and return ``str(expression)``.

        Base64-encodes the script so neither the host shell nor the user's
        remote shell can mangle quoting or metacharacters inside the
        expression. The remote one-liner just decodes and exec()s it.
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
