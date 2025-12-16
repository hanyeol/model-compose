from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Union, Any
from mindor.core.logger import logging
import asyncio
import os
import threading
from enum import Enum
from dataclasses import dataclass

if TYPE_CHECKING:
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

    def __init__(self, username: str, keyfile: str):
        self.type = SshAuthType.KEYFILE
        self.username = username
        self.keyfile = keyfile

    def to_params(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "key_filename": os.path.expanduser(self.keyfile)
        }

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
    """SSH client with remote port forwarding support"""
    shared_instance: Optional["SshClient"] = None

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
            The actual remote port bound (may differ if remote_port was 0)
        """
        def _start_forwarding():
            # Define handler for this specific port forward
            def port_forward_handler(channel, _, server_addr):
                """Handler called when a connection is made to the forwarded port"""
                server_port = server_addr[1]
                if server_port in self.port_forwards:
                    fwd_local_host, fwd_local_port = self.port_forwards[server_port]
                    forward_thread = threading.Thread(
                        target=self._handle_forward,
                        args=(channel, fwd_local_host, fwd_local_port),
                        daemon=True
                    )
                    forward_thread.start()
                    self._forward_threads.append(forward_thread)
                else:
                    logging.warning(f"Unknown remote port: {server_port}, closing channel")
                    channel.close()

            actual_remote_port = self.transport.request_port_forward(
                address="0.0.0.0",  # Bind to all interfaces on remote
                port=remote_port,
                handler=port_forward_handler
            )

            self.port_forwards[actual_remote_port] = (local_host, local_port)

            logging.debug(
                f"Remote port forwarding: {self.params.host}:{actual_remote_port} -> {local_host}:{local_port}"
            )

            return actual_remote_port

        return await asyncio.to_thread(_start_forwarding)

    def _handle_forward(
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

    @classmethod
    def get_shared_instance(cls, params: SshConnectionParams) -> "SshClient":
        """Get or create shared SSH client instance"""
        if not cls.shared_instance:
            cls.shared_instance = SshClient(params)
        return cls.shared_instance
