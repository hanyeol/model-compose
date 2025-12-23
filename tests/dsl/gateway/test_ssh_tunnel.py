import pytest
from mindor.dsl.schema.gateway import SshTunnelGatewayConfig
from mindor.dsl.schema.transport.ssh import SshKeyfileAuthConfig, SshPasswordAuthConfig

class TestSshTunnelGatewayConfig:
    """Test SshTunnelGatewayConfig port normalization"""

    def test_single_int_port(self):
        """Test single integer port: 5432 -> [(5432, 5432)]"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=5432,
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(5432, 5432)]

    def test_single_string_port(self):
        """Test single string port: '8080:5432' -> [(8080, 5432)]"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port="8080:5432",
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(8080, 5432)]

    def test_list_of_multiple_ints(self):
        """Test list of multiple single ports: [5432, 6379, 3306]"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=[5432, 6379, 3306],
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(5432, 5432), (6379, 6379), (3306, 3306)]

    def test_list_of_strings(self):
        """Test list of string ports: ['8080:5432', '9090:6379']"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=["8080:5432", "9090:6379"],
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(8080, 5432), (9090, 6379)]

    def test_mixed_list(self):
        """Test mixed list: [5432, '8080:3306', 6379]"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=[5432, "8080:3306", 6379],
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(5432, 5432), (8080, 3306), (6379, 6379)]

    def test_complex_port_ranges(self):
        """Test complex port forwarding scenarios"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=["15432:5432", "16379:6379", "13306:3306"],
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(15432, 5432), (16379, 6379), (13306, 3306)]

    def test_keyfile_auth(self):
        """Test SSH keyfile authentication"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=5432,
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert isinstance(config.connection.auth, SshKeyfileAuthConfig)
        assert config.connection.auth.username == "deploy"
        assert config.connection.auth.keyfile == "~/.ssh/id_rsa"

    def test_password_auth(self):
        """Test SSH password authentication"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=5432,
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "password",
                    "username": "deploy",
                    "password": "secret123"
                }
            }
        )

        assert isinstance(config.connection.auth, SshPasswordAuthConfig)
        assert config.connection.auth.username == "deploy"
        assert config.connection.auth.password == "secret123"

    def test_custom_ssh_port(self):
        """Test custom SSH port"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=5432,
            connection={
                "host": "bastion.example.com",
                "port": 2222,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.connection.port == 2222

    def test_default_ssh_port(self):
        """Test default SSH port (22)"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=5432,
            connection={
                "host": "bastion.example.com",
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.connection.port == 22

    def test_high_port_numbers(self):
        """Test high port numbers"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port="65000:65535",
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(65000, 65535)]

    def test_multiple_same_local_ports(self):
        """Test multiple forwards with same local port to different remote ports"""
        config = SshTunnelGatewayConfig(
            type="ssh-tunnel",
            port=["8080:5432", "8081:3306", "8082:6379"],
            connection={
                "host": "bastion.example.com",
                "port": 22,
                "auth": {
                    "type": "keyfile",
                    "username": "deploy",
                    "keyfile": "~/.ssh/id_rsa"
                }
            }
        )

        assert config.port == [(8080, 5432), (8081, 3306), (8082, 6379)]

    def test_empty_list_should_fail(self):
        """Test that empty port list raises validation error"""
        with pytest.raises(Exception):  # Pydantic will raise validation error
            SshTunnelGatewayConfig(
                type="ssh-tunnel",
                port=[],
                connection={
                    "host": "bastion.example.com",
                    "port": 22,
                    "auth": {
                        "type": "keyfile",
                        "username": "deploy",
                        "keyfile": "~/.ssh/id_rsa"
                    }
                }
            )

    def test_invalid_port_string_format(self):
        """Test invalid port string format"""
        with pytest.raises(Exception):  # Should fail on int conversion
            SshTunnelGatewayConfig(
                type="ssh-tunnel",
                port="invalid:port",
                connection={
                    "host": "bastion.example.com",
                    "port": 22,
                    "auth": {
                        "type": "keyfile",
                        "username": "deploy",
                        "keyfile": "~/.ssh/id_rsa"
                    }
                }
            )

    def test_three_part_port_string(self):
        """Test three-part port string should fail (invalid format)"""
        with pytest.raises(Exception):  # Should fail - only local:remote format is valid
            SshTunnelGatewayConfig(
                type="ssh-tunnel",
                port="8080:5432:1234",  # Invalid: too many parts
                connection={
                    "host": "bastion.example.com",
                    "port": 22,
                    "auth": {
                        "type": "keyfile",
                        "username": "deploy",
                        "keyfile": "~/.ssh/id_rsa"
                    }
                }
            )