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

    async def resolve_executable(
        self,
        executable: str = "python",
        working_dir: Optional[str] = None,
        timeout: float = 10.0,
    ) -> str:
        """Return the absolute path of the Python executable visible to the
        remote user's **interactive** login shell.

        The remote host may rely on shell init (``.bashrc``, pyenv init,
        conda hook, Windows ``$PROFILE``) to put a ``python`` on PATH, so
        a plain ``exec_command`` — which runs non-interactively and skips
        those files — would see a stripped environment. This method
        instead opens an interactive shell via ``invoke_shell`` so the
        user's init runs, then asks ``python`` to print its own
        ``sys.executable`` wrapped in sentinels, parses the result, and
        hangs up.

        The returned path is the absolute location of the real
        executable binary (not a shim), so later ``exec_command`` calls
        can invoke it directly without re-running shell init.
        """
        return await self._evaluate_expression(
            executable,
            "__import__('sys').executable",
            working_dir=working_dir,
            timeout=timeout
        )

    async def resolve_site_packages_path(
        self,
        executable: str,
        working_dir: Optional[str] = None,
        timeout: float = 10.0,
    ) -> str:
        """Return the remote python's ``purelib`` site-packages directory.

        Pass the ``executable`` returned by `resolve_executable` (or
        the python inside a venv when provisioning that venv). Useful for
        placing ``.pth`` files or dropping a mirrored package without
        asking pip.
        """
        return await self._evaluate_expression(
            executable,
            "__import__('sysconfig').get_paths()['purelib']",
            working_dir=working_dir,
            timeout=timeout,
        )

    async def resolve_mindor_source_path(
        self,
        executable: str,
        working_dir: Optional[str] = None,
        timeout: float = 10.0,
    ) -> str:
        """Return the ``mindor`` package directory on the remote
        (``.../src/mindor``).

        Pass the ``executable`` returned by `resolve_executable`
        so the two probes agree on the same binary (and the shell init
        runs once rather than twice). Take the ``.parent`` of the result
        to get what goes into a ``mindor.pth`` file.
        """
        return await self._evaluate_expression(
            executable,
            "__import__('pathlib').Path(__import__('mindor').__file__).parent",
            working_dir=working_dir,
            timeout=timeout,
        )

    async def _evaluate_expression(
        self,
        executable: str,
        expression: str,
        working_dir: Optional[str] = None,
        timeout: float = 10.0,
    ) -> str:
        """Evaluate ``expression`` in a remote python running under the
        user's interactive shell, and return ``str(expression)``."""
        import base64

        # Base64 the script so neither the host shell nor the user's remote
        # shell can mangle quoting or metacharacters inside ``expression``.
        # The remote one-liner just decodes and exec()s it.
        sentinel = "MINDOR_" + uuid.uuid4().hex
        script = f'print("{sentinel}" + str({expression}) + "{sentinel}")'
        encoded_script = base64.b64encode(script.encode()).decode()
        command = f'{executable} -c "exec(__import__(\'base64\').b64decode(\'{encoded_script}\').decode())"'

        # Match the python echo of ``<sentinel><path><sentinel>`` and reject
        # the command-line echo, which has ``"`` around the sentinel literal.
        pattern = re.compile(re.escape(sentinel) + r'([^"\r\n]+?)' + re.escape(sentinel))

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

                raise RuntimeError(f"could not evaluate remote python expression within {timeout}s: {expression}")
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
