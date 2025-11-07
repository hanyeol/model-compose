import pytest
from unittest.mock import MagicMock, patch
from mindor.core.runtime.docker.docker import (
    DockerRuntimeManager,
    DockerPortsResolver,
    DockerMountsResolver,
)
from mindor.dsl.schema.runtime.impl.docker import (
    DockerRuntimeConfig,
    DockerPortConfig,
    DockerVolumeConfig,
)
from docker.errors import NotFound, DockerException
from docker.types import Mount


# Configure anyio to use only asyncio backend
@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestDockerPortsResolver:
    """Test DockerPortsResolver class"""

    def test_resolve_empty_ports(self):
        """Test resolving empty port list"""
        resolver = DockerPortsResolver(None)
        result = resolver.resolve()

        assert result == {}

    def test_resolve_empty_list(self):
        """Test resolving empty port list"""
        resolver = DockerPortsResolver([])
        result = resolver.resolve()

        assert result == {}

    def test_resolve_int_port(self):
        """Test resolving single integer port"""
        resolver = DockerPortsResolver([8080])
        result = resolver.resolve()

        assert result == { "8080": "8080" }

    def test_resolve_multiple_int_ports(self):
        """Test resolving multiple integer ports"""
        resolver = DockerPortsResolver([8080, 9090, 3000])
        result = resolver.resolve()

        assert result == {
            "8080": "8080",
            "9090": "9090",
            "3000": "3000"
        }

    def test_resolve_string_port(self):
        """Test resolving string port format 'published:target' (host:container)"""
        resolver = DockerPortsResolver(["80:8080"])
        result = resolver.resolve()

        assert result == { "8080": "80" }

    def test_resolve_multiple_string_ports(self):
        """Test resolving multiple string ports"""
        resolver = DockerPortsResolver([ "80:8080", "443:8443", "3306:3306" ])
        result = resolver.resolve()

        assert result == {
            "8080": "80",
            "8443": "443",
            "3306": "3306"
        }

    def test_resolve_port_config_with_published(self):
        """Test resolving DockerPortConfig with published port"""
        resolver = DockerPortsResolver([
            DockerPortConfig(target=8080, published=80)
        ])
        result = resolver.resolve()

        assert result == { "8080": "80" }

    def test_resolve_port_config_without_published(self):
        """Test resolving DockerPortConfig without published port"""
        resolver = DockerPortsResolver([
            DockerPortConfig(target=8080)
        ])
        result = resolver.resolve()

        assert result == {}

    def test_resolve_mixed_port_formats(self):
        """Test resolving mixed port formats"""
        resolver = DockerPortsResolver([
            8080,  # int
            "443:8443",  # string
            DockerPortConfig(target=3000, published=3001),  # object with published
            DockerPortConfig(target=5000),  # object without published
        ])
        result = resolver.resolve()

        assert result == {
            "8080": "8080",
            "8443": "443",
            "3000": "3001"
        }


class TestDockerMountsResolver:
    """Test DockerMountsResolver class"""

    def test_resolve_empty_volumes(self):
        """Test resolving empty volume list"""
        resolver = DockerMountsResolver(None)
        result = resolver.resolve()

        assert result == []

    def test_resolve_empty_list(self):
        """Test resolving empty volume list"""
        resolver = DockerMountsResolver([])
        result = resolver.resolve()

        assert result == []

    def test_resolve_string_volume(self):
        """Test resolving string volume format 'source:target'"""
        resolver = DockerMountsResolver(["/host/path:/container/path"])
        result = resolver.resolve()

        assert len(result) == 1
        assert isinstance(result[0], Mount)
        assert result[0]["Source"] == "/host/path"
        assert result[0]["Target"] == "/container/path"
        assert result[0]["Type"] == "bind"

    def test_resolve_multiple_string_volumes(self):
        """Test resolving multiple string volumes"""
        resolver = DockerMountsResolver([
            "/data:/app/data",
            "/logs:/app/logs",
        ])
        result = resolver.resolve()

        assert len(result) == 2
        assert result[0]["Source"] == "/data"
        assert result[0]["Target"] == "/app/data"
        assert result[1]["Source"] == "/logs"
        assert result[1]["Target"] == "/app/logs"

    def test_resolve_bind_volume_config(self):
        """Test resolving bind volume configuration"""
        resolver = DockerMountsResolver([
            DockerVolumeConfig(
                type="bind",
                source="/host/path",
                target="/container/path",
                read_only=True
            )
        ])
        result = resolver.resolve()

        assert len(result) == 1
        assert result[0]["Type"] == "bind"
        assert result[0]["Source"] == "/host/path"
        assert result[0]["Target"] == "/container/path"
        assert result[0]["ReadOnly"] is True

    def test_resolve_bind_volume_config_without_readonly(self):
        """Test resolving bind volume without read_only"""
        resolver = DockerMountsResolver([
            DockerVolumeConfig(
                type="bind",
                source="/host/path",
                target="/container/path"
            )
        ])
        result = resolver.resolve()

        assert len(result) == 1
        assert result[0]["ReadOnly"] is False

    def test_resolve_named_volume_config(self):
        """Test resolving named volume configuration"""
        resolver = DockerMountsResolver([
            DockerVolumeConfig(
                type="volume",
                source="my-volume",
                target="/data",
                volume={ "nocopy": "true" }
            )
        ])
        result = resolver.resolve()

        # Named volumes (type="volume") are not added to mounts in current implementation
        # Only bind mounts are processed
        assert len(result) == 0

    def test_resolve_tmpfs_volume_config(self):
        """Test resolving tmpfs volume configuration"""
        resolver = DockerMountsResolver([
            DockerVolumeConfig(
                type="tmpfs",
                target="/tmp"
            )
        ])
        result = resolver.resolve()

        # tmpfs volumes are not added to mounts in current implementation
        # Only bind mounts are processed
        assert len(result) == 0

    def test_resolve_mixed_volume_formats(self):
        """Test resolving mixed volume formats"""
        resolver = DockerMountsResolver([
            "/data:/app/data",  # string
            DockerVolumeConfig(
                type="bind",
                source="/logs",
                target="/app/logs",
                read_only=True
            )
        ])
        result = resolver.resolve()

        assert len(result) == 2
        assert result[0]["Source"] == "/data"
        assert result[0]["Target"] == "/app/data"
        assert result[1]["Source"] == "/logs"
        assert result[1]["Target"] == "/app/logs"
        assert result[1]["ReadOnly"] is True


class TestDockerRuntimeManager:
    """Test DockerRuntimeManager class"""

    @pytest.fixture
    def config(self):
        """Create a basic Docker runtime config"""
        return DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container"
        )

    @pytest.fixture
    def mock_docker_client(self):
        """Create a mock Docker client"""
        with patch('mindor.core.runtime.docker.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_init(self, config, mock_docker_client):
        """Test DockerRuntimeManager initialization"""
        manager = DockerRuntimeManager(config, verbose=True)

        assert manager.config == config
        assert manager.verbose is True
        assert manager.client is not None

    async def test_exists_image_true(self, config, mock_docker_client, anyio_backend):
        """Test exists_image returns True when image exists"""
        mock_docker_client.images.get.return_value = MagicMock()

        manager = DockerRuntimeManager(config, verbose=False)
        result = await manager.exists_image()

        assert result is True
        mock_docker_client.images.get.assert_called_once_with("test-image:latest")

    
    async def test_exists_image_false(self, config, mock_docker_client, anyio_backend):
        """Test exists_image returns False when image doesn't exist"""
        mock_docker_client.images.get.side_effect = NotFound("Image not found")

        manager = DockerRuntimeManager(config, verbose=False)
        result = await manager.exists_image()

        assert result is False

    
    async def test_exists_container_true(self, config, mock_docker_client, anyio_backend):
        """Test exists_container returns True when container exists"""
        mock_docker_client.containers.get.return_value = MagicMock()

        manager = DockerRuntimeManager(config, verbose=False)
        result = await manager.exists_container()

        assert result is True
        mock_docker_client.containers.get.assert_called_once_with("test-container")

    
    async def test_exists_container_false(self, config, mock_docker_client, anyio_backend):
        """Test exists_container returns False when container doesn't exist"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = DockerRuntimeManager(config, verbose=False)
        result = await manager.exists_container()

        assert result is False

    
    async def test_is_container_running_true(self, config, mock_docker_client, anyio_backend):
        """Test is_container_running returns True when container is running"""
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_docker_client.containers.get.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        result = await manager.is_container_running()

        assert result is True

    
    async def test_is_container_running_false(self, config, mock_docker_client, anyio_backend):
        """Test is_container_running returns False when container is stopped"""
        mock_container = MagicMock()
        mock_container.status = "exited"
        mock_docker_client.containers.get.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        result = await manager.is_container_running()

        assert result is False

    
    async def test_is_container_running_not_found(self, config, mock_docker_client, anyio_backend):
        """Test is_container_running returns False when container doesn't exist"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = DockerRuntimeManager(config, verbose=False)
        result = await manager.is_container_running()

        assert result is False

    
    async def test_pull_image_success(self, config, mock_docker_client, anyio_backend):
        """Test successful image pull"""
        manager = DockerRuntimeManager(config, verbose=False)
        await manager.pull_image()

        mock_docker_client.images.pull.assert_called_once_with("test-image:latest")

    
    async def test_pull_image_failure(self, config, mock_docker_client, anyio_backend):
        """Test image pull failure"""
        mock_docker_client.images.pull.side_effect = DockerException("Pull failed")

        manager = DockerRuntimeManager(config, verbose=False)

        with pytest.raises(RuntimeError, match="Failed to pull image"):
            await manager.pull_image()

    
    async def test_remove_image_success(self, config, mock_docker_client, anyio_backend):
        """Test successful image removal"""
        manager = DockerRuntimeManager(config, verbose=False)
        await manager.remove_image()

        mock_docker_client.images.remove.assert_called_once_with(
            image="test-image:latest",
            force=False
        )

    
    async def test_remove_image_force(self, config, mock_docker_client, anyio_backend):
        """Test forced image removal"""
        manager = DockerRuntimeManager(config, verbose=False)
        await manager.remove_image(force=True)

        mock_docker_client.images.remove.assert_called_once_with(
            image="test-image:latest",
            force=True
        )

    
    async def test_remove_image_not_found(self, config, mock_docker_client, anyio_backend):
        """Test removing non-existent image doesn't raise error"""
        mock_docker_client.images.remove.side_effect = NotFound("Image not found")

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.remove_image()  # Should not raise

    
    async def test_stop_container_success(self, config, mock_docker_client, anyio_backend):
        """Test successful container stop"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.stop_container()

        mock_container.stop.assert_called_once()

    
    async def test_stop_container_not_found(self, config, mock_docker_client, anyio_backend):
        """Test stopping non-existent container doesn't raise error"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.stop_container()  # Should not raise

    
    async def test_remove_container_success(self, config, mock_docker_client, anyio_backend):
        """Test successful container removal"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.remove_container()

        mock_container.remove.assert_called_once_with(force=False)

    
    async def test_remove_container_force(self, config, mock_docker_client, anyio_backend):
        """Test forced container removal"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.remove_container(force=True)

        mock_container.remove.assert_called_once_with(force=True)

    
    async def test_start_container_creates_new(self, config, mock_docker_client, anyio_backend):
        """Test starting container creates new one if it doesn't exist"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")
        mock_container = MagicMock()
        mock_docker_client.containers.create.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.start_container(detach=True)

        mock_docker_client.containers.create.assert_called_once()
        mock_container.start.assert_called_once()

    
    async def test_start_container_uses_existing(self, config, mock_docker_client, anyio_backend):
        """Test starting container uses existing one"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.start_container(detach=True)

        mock_docker_client.containers.create.assert_not_called()
        mock_container.start.assert_called_once()

    
    async def test_start_container_with_ports(self, mock_docker_client, anyio_backend):
        """Test starting container with port mappings"""
        config = DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
            ports=[ 8080, "443:8443" ]
        )

        mock_docker_client.containers.get.side_effect = NotFound("Container not found")
        mock_container = MagicMock()
        mock_docker_client.containers.create.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.start_container(detach=True)

        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["ports"] == { "8080": "8080", "8443": "443" }

    
    async def test_start_container_with_environment(self, mock_docker_client, anyio_backend):
        """Test starting container with environment variables"""
        config = DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
            environment={ "ENV": "production", "DEBUG": False }
        )

        mock_docker_client.containers.get.side_effect = NotFound("Container not found")
        mock_container = MagicMock()
        mock_docker_client.containers.create.return_value = mock_container

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.start_container(detach=True)

        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["environment"] == { "ENV": "production", "DEBUG": False }

    
    async def test_build_image_success(self, mock_docker_client, anyio_backend):
        """Test successful image build"""
        config = DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            build={
                "context": ".",
                "dockerfile": "Dockerfile"
            }
        )

        mock_docker_client.api.build.return_value = [
            { "stream": "Step 1/2 : FROM python:3.11\n" },
            { "stream": "Step 2/2 : COPY . /app\n" },
        ]

        manager = DockerRuntimeManager(config, verbose=False)
        await manager.build_image()

        mock_docker_client.api.build.assert_called_once()

    
    async def test_build_image_with_error(self, mock_docker_client, anyio_backend):
        """Test image build with error"""
        config = DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            build={
                "context": ".",
                "dockerfile": "Dockerfile"
            }
        )

        mock_docker_client.api.build.return_value = [
            { "stream": "Step 1/2 : FROM python:3.11\n" },
            { "errorDetail": { "message": "Build failed" }},
        ]

        manager = DockerRuntimeManager(config, verbose=False)

        with pytest.raises(RuntimeError, match="Build failed"):
            await manager.build_image()
