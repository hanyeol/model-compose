"""
SSH client integration tests

Configure via environment variables:
    export SSH_TEST_HOST=your-ssh-server.com
    export SSH_TEST_PORT=22
    export SSH_TEST_USER=your-username
    export SSH_TEST_KEYFILE=~/.ssh/id_rsa
    # OR
    export SSH_TEST_PASSWORD=your-password

Run tests:
    pytest tests/core/utils/test_ssh_client.py -v -s
"""

import pytest
import os
import asyncio
import socket
from mindor.core.utils.ssh_client import SshClient
from mindor.dsl.schema.transport.ssh import SshConnectionConfig, SshKeyfileAuthConfig, SshPasswordAuthConfig

# Configure anyio to use only asyncio backend (disable trio)
@pytest.fixture
def anyio_backend():
    return "asyncio"

# SSH server configuration from environment
SSH_HOST     = os.getenv("SSH_TEST_HOST", "localhost")
SSH_PORT     = int(os.getenv("SSH_TEST_PORT", "22"))
SSH_USER     = os.getenv("SSH_TEST_USER", "test")
SSH_KEYFILE  = os.getenv("SSH_TEST_KEYFILE", "~/.ssh/id_rsa")
SSH_PASSWORD = os.getenv("SSH_TEST_PASSWORD", "")

def find_free_port():
    """Find a free local port"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


class TestSshClient:
    """SSH client integration tests"""

    @pytest.fixture
    def keyfile_connection_config(self):
        """SSH config with keyfile authentication"""
        return SshConnectionConfig(
            host=SSH_HOST,
            port=SSH_PORT,
            auth=SshKeyfileAuthConfig(
                type="keyfile",
                username=SSH_USER,
                keyfile=SSH_KEYFILE
            )
        )

    @pytest.fixture
    def password_connection_config(self):
        """SSH config with password authentication"""
        return SshConnectionConfig(
            host=SSH_HOST,
            port=SSH_PORT,
            auth=SshPasswordAuthConfig(
                type="password",
                username=SSH_USER,
                password=SSH_PASSWORD
            )
        )

    def test_create_instance(self, keyfile_connection_config):
        """Test SSH client instance creation"""
        client = SshClient(keyfile_connection_config)

        assert client.config == keyfile_connection_config
        assert client.client is None
        assert client.transport is None
        assert client.port_forwards == []
        assert client._shutdown_event is None
        assert client._forward_threads == []

    @pytest.mark.anyio
    async def test_connect_with_keyfile(self, keyfile_connection_config):
        """Test real SSH connection with keyfile"""
        client = SshClient(keyfile_connection_config)

        try:
            await client.connect()
            assert client.is_connected()
            assert client.client is not None
            assert client.transport is not None
            assert client._shutdown_event is not None
        finally:
            await client.close()

    @pytest.mark.anyio
    @pytest.mark.skipif(not SSH_PASSWORD, reason="Password auth not configured")
    async def test_connect_with_password(self, password_connection_config):
        """Test real SSH connection with password"""
        client = SshClient(password_connection_config)

        try:
            await client.connect()
            assert client.is_connected()
            assert client.client is not None
            assert client.transport is not None
        finally:
            await client.close()

    @pytest.mark.anyio
    async def test_is_connected(self, keyfile_connection_config):
        """Test is_connected returns correct status"""
        client = SshClient(keyfile_connection_config)

        # Before connection
        assert not client.is_connected()

        try:
            await client.connect()
            # After connection
            assert client.is_connected()
        finally:
            await client.close()
            # After closing
            assert not client.is_connected()

    @pytest.mark.anyio
    async def test_context_manager(self, keyfile_connection_config):
        """Test using SSH client as context manager"""
        async with SshClient(keyfile_connection_config) as client:
            assert client.is_connected()

        # Connection should be closed after context
        assert not client.is_connected()

    @pytest.mark.anyio
    async def test_remote_port_forwarding(self, keyfile_connection_config):
        """Test real remote port forwarding"""
        client = SshClient(keyfile_connection_config)

        # Start a simple local server
        local_port = find_free_port()
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("localhost", local_port))
        server_socket.listen(1)

        try:
            await client.connect()

            # Start remote port forwarding
            remote_port = find_free_port()
            remote_port = await client.start_remote_port_forwarding(
                remote_port=remote_port,
                local_port=local_port
            )

            print(f"\nRemote port forwarding: {SSH_HOST}:{remote_port} -> localhost:{local_port}")

            # Verify port forward was tracked
            assert (remote_port, local_port) in client.port_forwards
            assert len(client._forward_threads) > 0

            # Keep connection alive briefly
            await asyncio.sleep(1)

        finally:
            await client.close()
            server_socket.close()

    @pytest.mark.anyio
    async def test_multiple_port_forwards(self, keyfile_connection_config):
        """Test multiple remote port forwards"""
        client = SshClient(keyfile_connection_config)

        # Create multiple local servers
        num_forwards = 3
        local_ports = [find_free_port() for _ in range(num_forwards)]
        servers = []

        for port in local_ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('localhost', port))
            s.listen(1)
            servers.append(s)

        try:
            await client.connect()

            # Start multiple remote port forwards
            for local_port in local_ports:
                remote_port = find_free_port()
                remote_port = await client.start_remote_port_forwarding(
                    remote_port=remote_port,
                    local_port=local_port
                )
                print(f"\nForward {len(client.port_forwards)}: {SSH_HOST}:{remote_port} -> localhost:{local_port}")

            # Verify all forwards
            assert len(client.port_forwards) == num_forwards
            assert len(client._forward_threads) == num_forwards

            await asyncio.sleep(1)

        finally:
            await client.close()
            for s in servers:
                s.close()

    @pytest.mark.anyio
    async def test_close(self, keyfile_connection_config):
        """Test closing SSH connection"""
        client = SshClient(keyfile_connection_config)

        local_port = find_free_port()
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('localhost', local_port))
        server_socket.listen(1)

        try:
            await client.connect()
            remote_port = find_free_port()
            await client.start_remote_port_forwarding(remote_port, local_port)

            assert len(client.port_forwards) > 0
            assert client._shutdown_event is not None

            # Close and verify cleanup
            await client.close()

            assert client.client is None
            assert client.transport is None
            assert len(client.port_forwards) == 0
            assert client._shutdown_event is None

        finally:
            if client.is_connected():
                await client.close()
            server_socket.close()

    @pytest.mark.anyio
    async def test_reconnect_after_close(self, keyfile_connection_config):
        """Test reconnecting after closing connection"""
        client = SshClient(keyfile_connection_config)

        # First connection
        await client.connect()
        assert client.is_connected()
        await client.close()
        assert not client.is_connected()

        # Reconnect
        await client.connect()
        assert client.is_connected()
        await client.close()

    @pytest.mark.anyio
    async def test_dynamic_port_allocation(self, keyfile_connection_config):
        """Test remote port forwarding with dynamic port (0)"""
        client = SshClient(keyfile_connection_config)

        local_port = find_free_port()
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('localhost', local_port))
        server_socket.listen(1)

        try:
            await client.connect()

            # Request dynamic port allocation (port=0)
            remote_port = await client.start_remote_port_forwarding(
                remote_port=0,  # Let SSH server choose port
                local_port=local_port
            )

            print(f"\nDynamic port allocated: {SSH_HOST}:{remote_port} -> localhost:{local_port}")

            # Verify dynamic port was assigned
            assert remote_port > 0
            assert (remote_port, local_port) in client.port_forwards

        finally:
            await client.close()
            server_socket.close()

    def test_get_shared_instance(self, keyfile_connection_config):
        """Test getting shared instance"""
        # Clear any existing shared instance
        SshClient.shared_instance = None

        instance1 = SshClient.get_shared_instance(keyfile_connection_config)
        instance2 = SshClient.get_shared_instance(keyfile_connection_config)

        # Verify same instance is returned
        assert instance1 is instance2

        # Cleanup
        SshClient.shared_instance = None
