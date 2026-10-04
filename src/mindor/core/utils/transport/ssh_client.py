from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Union, Any
from collections.abc import AsyncIterable, AsyncIterator
from enum import Enum
from dataclasses import dataclass
from mindor.core.logger import logging
import asyncio, os, shlex, threading

if TYPE_CHECKING:
    from paramiko.channel import ChannelStdinFile
    import paramiko

class SshAuthType(str, Enum):
    """SSH authentication type"""
    KEYFILE  = "keyfile"
    PASSWORD = "password"

@dataclass
class SshAuthParams:
    """Base SSH authentication parameters"""
    type: SshAuthType

    def to_params(self) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement to_params()")

@dataclass
class SshKeyfileAuthParams(SshAuthParams):
    """SSH keyfile authentication parameters"""
    username: str
    keyfile: str
    passphrase: Optional[str] = None

    def __init__(self, username: str, keyfile: str, passphrase: Optional[str] = None):
        self.type = SshAuthType.KEYFILE
        self.username = username
        self.keyfile = keyfile
        self.passphrase = passphrase

    def to_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "username": self.username,
            "key_filename": os.path.expanduser(self.keyfile)
        }

        if self.passphrase is not None:
            params["passphrase"] = self.passphrase

        return params

@dataclass
class SshPasswordAuthParams(SshAuthParams):
    """SSH password authentication parameters"""
    username: str
    password: str

    def __init__(self, username: str, password: str):
        self.type = SshAuthType.PASSWORD
        self.username = username
        self.password = password

    def to_params(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "password": self.password
        }

@dataclass
class SshConnectionParams:
    """SSH connection parameters"""
    host: str
    auth: Union[SshKeyfileAuthParams, SshPasswordAuthParams]
    port: int = 22
    keepalive_interval: int = 0  # Send keepalive every N seconds (0 to disable)

    def to_params(self) -> Dict[str, Any]:
        return {
            "hostname": self.host,
            "port": self.port,
            **self.auth.to_params()
        }

class SshClient:
    def __init__(self, params: SshConnectionParams):
        self.params: SshConnectionParams = params
        self.client: Optional[paramiko.SSHClient] = None
        self.transport: Optional[paramiko.Transport] = None
        self.port_forwards: Dict[int, Tuple[str, int]] = {}  # remote_port -> (local_host, local_port)

        self._shutdown_event: Optional[threading.Event] = None
        self._forward_threads: List[threading.Thread] = []

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self) -> None:
        """Establish SSH connection"""
        import paramiko

        def _connect():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            logging.debug(f"Connecting to {self.params.host}:{self.params.port}...")
            client.connect(**self.params.to_params())

            # Set keepalive if enabled
            if self.params.keepalive_interval > 0:
                transport = client.get_transport()
                transport.set_keepalive(self.params.keepalive_interval)
                logging.debug(f"SSH keepalive enabled: {self.params.keepalive_interval}s interval")

            logging.debug(f"SSH connection established to {self.params.host}:{self.params.port}")

            return client

        self.client = await asyncio.to_thread(_connect)
        self.transport = self.client.get_transport()

        self._shutdown_event = threading.Event()

    async def run_command(
        self,
        command: List[str],
        stdin: Optional[AsyncIterable[bytes]] = None,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, bytes, int]:
        """Execute a command on the remote host and return (stdout, stderr, exit_code).

        argv is joined with shlex.quote; working_dir and env are applied by
        prefixing `cd ... && VAR=... exec ...` since paramiko's exec_command
        runs a single shell command string. `stdin` is an optional async
        byte stream fed to the remote process's standard input.
        """
        remote_command = self._build_remote_command(command, working_dir, env)
        remote_stdin, remote_stdout, remote_stderr = await asyncio.to_thread(
            self.client.exec_command,
            remote_command,
            timeout=timeout
        )

        stdin_feeder = asyncio.create_task(self._feed_remote_stdin(remote_stdin, stdin)) if stdin is not None else None

        try:
            stdout, stderr = await asyncio.gather(
                asyncio.to_thread(remote_stdout.read),
                asyncio.to_thread(remote_stderr.read),
            )

            exit_code = await asyncio.to_thread(remote_stdout.channel.recv_exit_status)
        finally:
            if stdin_feeder is not None and not stdin_feeder.done():
                stdin_feeder.cancel()

                try:
                    await stdin_feeder
                except (asyncio.CancelledError, Exception):
                    pass

        return stdout, stderr, exit_code

    async def stream_command(
        self,
        command: List[str],
        stdin: Optional[AsyncIterable[bytes]] = None,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """Yield stdout lines from a remote command as they are produced.

        `timeout` acts as a per-line idle timeout, matching the local shell
        driver's semantics. `stdin` is an optional async byte stream fed to
        the remote process's standard input.
        """
        remote_command = self._build_remote_command(command, working_dir, env)
        remote_stdin, remote_stdout, remote_stderr = await asyncio.to_thread(
            self.client.exec_command,
            remote_command,
            timeout=timeout
        )

        logging.debug(f"Streaming remote command on {self.params.host}:{self.params.port}: {remote_command}")

        stdin_feeder = asyncio.create_task(self._feed_remote_stdin(remote_stdin, stdin)) if stdin is not None else None

        try:
            while True:
                line = await asyncio.wait_for(asyncio.to_thread(remote_stdout.readline), timeout=timeout)

                if not line:
                    break

                yield line
        finally:
            if stdin_feeder is not None and not stdin_feeder.done():
                stdin_feeder.cancel()

                try:
                    await stdin_feeder
                except (asyncio.CancelledError, Exception):
                    pass

            exit_code = await asyncio.to_thread(remote_stdout.channel.recv_exit_status)

            if exit_code != 0:
                stderr = await asyncio.to_thread(remote_stderr.read)

                logging.warning(
                    f"Remote command exited with code {exit_code}: {stderr.decode(errors='replace').strip()}"
                )

    async def start_remote_port_forwarding(
        self,
        remote_port: int,
        local_port: int,
        local_host: str = "localhost"
    ) -> int:
        """
        Start remote port forwarding

        Args:
            remote_port: Port on the remote SSH server
            local_port: Port on the local machine to forward to
            local_host: Local host address (default: localhost)

        Returns:
            The remote port actually bound (may differ if remote_port was 0)
        """
        def _start_forwarding():
            # Define handler for this specific port forward
            def _port_forward_handler(channel, _, server_addr):
                """Handler called when a connection is made to the forwarded port"""
                server_port = server_addr[1]
                if server_port in self.port_forwards:
                    forward_local_host, forward_local_port = self.port_forwards[server_port]
                    forward_thread = threading.Thread(
                        target=self._handle_forward_channel,
                        args=(channel, forward_local_host, forward_local_port),
                        daemon=True
                    )
                    forward_thread.start()
                    self._forward_threads.append(forward_thread)
                else:
                    logging.warning(f"Unknown remote port: {server_port}, closing channel")
                    channel.close()

            bound_remote_port = self.transport.request_port_forward(
                address="0.0.0.0",  # Bind to all interfaces on remote
                port=remote_port,
                handler=_port_forward_handler
            )

            self.port_forwards[bound_remote_port] = (local_host, local_port)

            logging.debug(
                f"Remote port forwarding: {self.params.host}:{bound_remote_port} -> {local_host}:{local_port}"
            )

            return bound_remote_port

        return await asyncio.to_thread(_start_forwarding)

    async def close(self) -> None:
        """Close SSH connection and stop all port forwarding"""
        if self._shutdown_event:
            self._shutdown_event.set()

        def _close():
            # Cancel all remote port forwards
            for remote_port in self.port_forwards.keys():
                try:
                    self.transport.cancel_port_forward("0.0.0.0", remote_port)
                    logging.debug(f"Cancelled remote port forward on port {remote_port}")
                except Exception as e:
                    logging.warning(f"Error cancelling port forward {remote_port}: {e}")

            if self.client:
                self.client.close()
                logging.debug(f"SSH connection closed to {self.params.host}:{self.params.port}")

        if self.client:
            await asyncio.to_thread(_close)

        self.client = None
        self.transport = None
        self.port_forwards = {}

        self._forward_threads = []
        self._shutdown_event = None

    def is_connected(self) -> bool:
        """Check if SSH connection is active"""
        return self.client is not None and self.transport is not None and self.transport.is_active()

    def _build_remote_command(
        self,
        command: List[str],
        working_dir: Optional[str],
        env: Optional[Dict[str, str]],
    ) -> str:
        parts: List[str] = []

        if working_dir:
            parts.append(f"cd {self._quote_remote_path(working_dir)} &&")

        if env:
            for name, value in env.items():
                parts.append(f"{name}={shlex.quote(str(value))}")

        parts.append("exec")
        parts.extend(shlex.quote(arg) for arg in command)

        return " ".join(parts)

    async def _feed_remote_stdin(self, stdin: ChannelStdinFile, source: AsyncIterable[bytes]) -> None:
        try:
            async for chunk in source:
                try:
                    await asyncio.to_thread(stdin.write, chunk)
                    await asyncio.to_thread(stdin.flush)
                except (OSError, EOFError):
                    break
        finally:
            try:
                await asyncio.to_thread(stdin.channel.shutdown_write)
            except Exception:
                pass
            try:
                await asyncio.to_thread(stdin.close)
            except Exception:
                pass

    def _handle_forward_channel(
        self,
        remote_channel: paramiko.Channel,
        local_host: str,
        local_port: int
    ) -> None:
        """Handle a single forwarded connection using select for bidirectional forwarding"""
        import socket
        import select

        local_socket = None
        try:
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local_socket.connect((local_host, local_port))

            # Non-blocking bidirectional forwarding using select
            while True:
                # Wait for either socket to have data ready (1 second timeout)
                r, _, _ = select.select([ remote_channel, local_socket ], [], [], 1.0)

                # Forward data from remote to local
                if remote_channel in r:
                    data = remote_channel.recv(8192)
                    if len(data) == 0:
                        break
                    local_socket.sendall(data)

                # Forward data from local to remote
                if local_socket in r:
                    data = local_socket.recv(8192)
                    if len(data) == 0:
                        break
                    remote_channel.sendall(data)

        except socket.error as e:
            logging.debug(f"Socket error in forward: {e}")
        except Exception as e:
            logging.error(f"Error handling forward connection: {e}")
        finally:
            # Clean up connections
            if local_socket:
                try:
                    local_socket.close()
                except Exception:
                    pass
            try:
                remote_channel.close()
            except Exception:
                pass

    def _quote_remote_path(self, path: str) -> str:
        # Preserve a leading `~` / `~user` segment unquoted so the remote login
        # shell performs tilde expansion; quote the rest so spaces and metachars
        # in the path can't break the command.
        if path.startswith("~"):
            head, separator, tail = path.partition("/")

            if separator and tail:
                return head + separator + shlex.quote(tail)

            return head

        return shlex.quote(path)
