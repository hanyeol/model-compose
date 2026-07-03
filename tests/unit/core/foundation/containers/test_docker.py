"""Tests for the Docker container helpers in `core.foundation.containers.docker`:
`DockerPortsResolver`, `DockerMountsResolver`, `DockerDeviceRequestsResolver`,
`DockerImageBuilder`, and `DockerContainerRunner`."""

import pytest

from unittest.mock import MagicMock, patch

from docker.errors import NotFound, DockerException
from docker.types import Mount
from mindor.core.foundation.containers.docker import (
    DockerContainerRunner,
    DockerContainerParams,
    DockerImageBuilder,
    DockerPortsResolver,
    DockerMountsResolver,
)
from mindor.dsl.schema.runtime.impl.docker import DockerRuntimeConfig
from mindor.dsl.schema.containers.docker import (
    DockerPortConfig,
    DockerVolumeConfig,
    DockerVolumeOptionsConfig,
    DockerTmpfsOptionsConfig,
)


def _runtime(config, verbose: bool = False) -> DockerContainerRunner:
    """Test helper — builds a `DockerContainerRunner` from a DSL config the
    same way a manager would: translate to `DockerContainerParams` first."""
    return DockerContainerRunner(DockerContainerParams.from_config(config), verbose=verbose)


def _builder() -> DockerImageBuilder:
    return DockerImageBuilder(verbose=False)


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


class TestDockerPortsResolver:
    """Test DockerPortsResolver class."""

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

    def test_resolve_port_config_with_host_port(self):
        """Test resolving DockerPortConfig with host_port"""
        resolver = DockerPortsResolver([
            DockerPortConfig(container_port=8080, host_port=80)
        ])
        result = resolver.resolve()

        assert result == { "8080/tcp": "80" }

    def test_resolve_port_config_without_host_port(self):
        """Test resolving DockerPortConfig without host_port"""
        resolver = DockerPortsResolver([
            DockerPortConfig(container_port=8080)
        ])
        result = resolver.resolve()

        assert result == {}

    def test_resolve_port_config_with_host_ip(self):
        """Test resolving DockerPortConfig with host_ip binds to a specific interface"""
        resolver = DockerPortsResolver([
            DockerPortConfig(container_port=8080, host_port=80, host_ip="127.0.0.1")
        ])
        result = resolver.resolve()

        assert result == { "8080/tcp": ("127.0.0.1", 80) }

    def test_resolve_mixed_port_formats(self):
        """Test resolving mixed port formats"""
        resolver = DockerPortsResolver([
            8080,  # int
            "443:8443",  # string
            DockerPortConfig(container_port=3000, host_port=3001),  # object with host_port
            DockerPortConfig(container_port=5000),  # object without host_port
        ])
        result = resolver.resolve()

        assert result == {
            "8080": "8080",
            "8443": "443",
            "3000/tcp": "3001"
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
                volume=DockerVolumeOptionsConfig(nocopy=True)
            )
        ])
        result = resolver.resolve()

        assert len(result) == 1
        assert result[0]["Target"] == "/data"
        assert result[0]["Source"] == "my-volume"
        assert result[0]["Type"] == "volume"

    def test_resolve_tmpfs_volume_config(self):
        """Test resolving tmpfs volume configuration"""
        resolver = DockerMountsResolver([
            DockerVolumeConfig(
                type="tmpfs",
                target="/tmp"
            )
        ])
        result = resolver.resolve()

        assert len(result) == 1
        assert result[0]["Target"] == "/tmp"
        assert result[0]["Type"] == "tmpfs"

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


@pytest.mark.anyio
class TestDockerContainerRunner:
    """Test DockerContainerRunner class"""

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
        with patch('mindor.core.foundation.containers.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_init(self, config, mock_docker_client):
        """Test DockerContainerRunner initialization"""
        manager = _runtime(config, verbose=True)

        assert manager.params.image == config.image
        assert manager.params.container_name == config.container_name
        assert manager.verbose is True
        assert manager._client is not None

    async def test_exists_image_true(self, config, mock_docker_client):
        """Test exists returns True when image exists"""
        mock_docker_client.images.get.return_value = MagicMock()

        builder = _builder()
        result = await builder.exists("test-image:latest")

        assert result is True
        mock_docker_client.images.get.assert_called_once_with("test-image:latest")


    async def test_exists_image_false(self, config, mock_docker_client):
        """Test exists returns False when image doesn't exist"""
        mock_docker_client.images.get.side_effect = NotFound("Image not found")

        builder = _builder()
        result = await builder.exists("test-image:latest")

        assert result is False

    
    async def test_exists_container_true(self, config, mock_docker_client):
        """Test exists_container returns True when container exists"""
        mock_docker_client.containers.get.return_value = MagicMock()

        manager = _runtime(config, verbose=False)
        result = await manager.exists()

        assert result is True
        mock_docker_client.containers.get.assert_called_once_with("test-container")

    
    async def test_exists_container_false(self, config, mock_docker_client):
        """Test exists_container returns False when container doesn't exist"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = _runtime(config, verbose=False)
        result = await manager.exists()

        assert result is False

    
    async def test_is_container_running_true(self, config, mock_docker_client):
        """Test is_container_running returns True when container is running"""
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config, verbose=False)
        result = await manager.is_running()

        assert result is True

    
    async def test_is_container_running_false(self, config, mock_docker_client):
        """Test is_container_running returns False when container is stopped"""
        mock_container = MagicMock()
        mock_container.status = "exited"
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config, verbose=False)
        result = await manager.is_running()

        assert result is False

    
    async def test_is_container_running_not_found(self, config, mock_docker_client):
        """Test is_container_running returns False when container doesn't exist"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = _runtime(config, verbose=False)
        result = await manager.is_running()

        assert result is False

    
    async def test_pull_image_success(self, config, mock_docker_client):
        """Test successful image pull"""
        builder = _builder()
        await builder.pull("test-image:latest")

        mock_docker_client.images.pull.assert_called_once_with("test-image:latest")


    async def test_pull_image_failure(self, config, mock_docker_client):
        """Test image pull failure"""
        mock_docker_client.images.pull.side_effect = DockerException("Pull failed")

        builder = _builder()

        with pytest.raises(RuntimeError, match="Failed to pull image"):
            await builder.pull("test-image:latest")


    async def test_remove_image_success(self, config, mock_docker_client):
        """Test successful image removal"""
        builder = _builder()
        await builder.remove("test-image:latest")

        mock_docker_client.images.remove.assert_called_once_with(
            image="test-image:latest",
            force=False
        )


    async def test_remove_image_force(self, config, mock_docker_client):
        """Test forced image removal"""
        builder = _builder()
        await builder.remove("test-image:latest", force=True)

        mock_docker_client.images.remove.assert_called_once_with(
            image="test-image:latest",
            force=True
        )


    async def test_remove_image_not_found(self, config, mock_docker_client):
        """Test removing non-existent image doesn't raise error"""
        mock_docker_client.images.remove.side_effect = NotFound("Image not found")

        builder = _builder()
        await builder.remove("test-image:latest")  # Should not raise

    
    async def test_stop_container_success(self, config, mock_docker_client):
        """Test successful container stop"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config, verbose=False)
        await manager.stop()

        mock_container.stop.assert_called_once()

    
    async def test_stop_container_not_found(self, config, mock_docker_client):
        """Test stopping non-existent container doesn't raise error"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = _runtime(config, verbose=False)
        await manager.stop()  # Should not raise

    
    async def test_remove_container_success(self, config, mock_docker_client):
        """Test successful container removal"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config, verbose=False)
        await manager.remove()

        mock_container.remove.assert_called_once_with(force=False)

    
    async def test_remove_container_force(self, config, mock_docker_client):
        """Test forced container removal"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config, verbose=False)
        await manager.remove(force=True)

        mock_container.remove.assert_called_once_with(force=True)

    
    async def test_start_container_creates_new(self, config, mock_docker_client):
        """Test starting container creates new one if it doesn't exist"""
        created_container = MagicMock()
        mock_docker_client.containers.get.side_effect = [
            NotFound("Container not found"),
            created_container,
        ]
        mock_docker_client.containers.create.return_value = created_container

        manager = _runtime(config, verbose=False)
        await manager.create()
        await manager.start(detach=True)

        mock_docker_client.containers.create.assert_called_once()
        created_container.start.assert_called_once()


    async def test_start_container_uses_existing(self, config, mock_docker_client):
        """Test starting container uses existing one"""
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config, verbose=False)
        await manager.create()
        await manager.start(detach=True)

        mock_docker_client.containers.create.assert_not_called()
        mock_container.start.assert_called_once()

    
    async def test_start_container_with_ports(self, mock_docker_client):
        """Test starting container with port mappings"""
        config = DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
            ports=[ 8080, "443:8443" ]
        )

        created_container = MagicMock()
        mock_docker_client.containers.get.side_effect = [
            NotFound("Container not found"),
            created_container,
        ]
        mock_docker_client.containers.create.return_value = created_container

        manager = _runtime(config, verbose=False)
        await manager.create()
        await manager.start(detach=True)

        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["ports"] == { "8080": "8080", "8443": "443" }

    
    async def test_start_container_with_environment(self, mock_docker_client):
        """Test starting container with environment variables"""
        config = DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
            environment={ "ENV": "production", "DEBUG": False }
        )

        created_container = MagicMock()
        mock_docker_client.containers.get.side_effect = [
            NotFound("Container not found"),
            created_container,
        ]
        mock_docker_client.containers.create.return_value = created_container

        manager = _runtime(config, verbose=False)
        await manager.create()
        await manager.start(detach=True)

        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["environment"] == { "ENV": "production", "DEBUG": False }

    
    async def test_build_image_success(self, mock_docker_client):
        """Test successful image build"""
        mock_docker_client.api.build.return_value = [
            { "stream": "Step 1/2 : FROM python:3.11\n" },
            { "stream": "Step 2/2 : COPY . /app\n" },
        ]

        builder = _builder()
        await builder.build(tag="test-image:latest", path=".", dockerfile="Dockerfile")

        mock_docker_client.api.build.assert_called_once()


    async def test_build_image_with_error(self, mock_docker_client):
        """Test image build with error"""
        mock_docker_client.api.build.return_value = [
            { "stream": "Step 1/2 : FROM python:3.11\n" },
            { "errorDetail": { "message": "Build failed" }},
        ]

        builder = _builder()

        with pytest.raises(RuntimeError, match="Build failed"):
            await builder.build(tag="test-image:latest", path=".", dockerfile="Dockerfile")


# ---------------------------------------------------------------------------
# get_container — escape hatch returning a Container, raising on miss
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestGetContainer:
    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    def config(self):
        return DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
        )

    @pytest.fixture
    def mock_docker_client(self):
        with patch('mindor.core.foundation.containers.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_returns_container_when_found(self, config, mock_docker_client):
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config)
        result = manager.get_container()

        assert result is mock_container
        mock_docker_client.containers.get.assert_called_once_with("test-container")

    def test_raises_runtimeerror_when_not_found(self, config, mock_docker_client):
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = _runtime(config)

        with pytest.raises(RuntimeError, match="does not exist"):
            manager.get_container()

    def test_wraps_dockerexception(self, config, mock_docker_client):
        mock_docker_client.containers.get.side_effect = DockerException("daemon offline")

        manager = _runtime(config)

        with pytest.raises(RuntimeError, match="Failed to get container"):
            manager.get_container()


# ---------------------------------------------------------------------------
# remove_container — idempotency invariant
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestRemoveContainerIdempotency:
    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    def config(self):
        return DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
        )

    @pytest.fixture
    def mock_docker_client(self):
        with patch('mindor.core.foundation.containers.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    async def test_remove_not_found_is_silent(self, config, mock_docker_client):
        """Removing a container that's already gone must not raise."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        manager = _runtime(config)
        await manager.remove(force=True)  # must not raise

    async def test_remove_race_during_remove_is_silent(self, config, mock_docker_client):
        """If the container disappears between `get` and `remove`, still no raise."""
        mock_container = MagicMock()
        mock_container.remove.side_effect = NotFound("disappeared")
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config)
        await manager.remove(force=True)  # must not raise

    async def test_remove_dockerexception_wraps(self, config, mock_docker_client):
        mock_container = MagicMock()
        mock_container.remove.side_effect = DockerException("daemon offline")
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config)
        with pytest.raises(RuntimeError, match="Failed to remove container"):
            await manager.remove()


# ---------------------------------------------------------------------------
# start_container(detach=False) — foreground path is invoked
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestStartContainerForeground:
    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    def config(self):
        return DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
        )

    @pytest.fixture
    def mock_docker_client(self):
        with patch('mindor.core.foundation.containers.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    async def test_detach_true_skips_foreground(self, config, mock_docker_client):
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config)
        from unittest.mock import AsyncMock
        manager._run_foreground_container = AsyncMock()

        await manager.start(detach=True)

        mock_container.start.assert_called_once()
        manager._run_foreground_container.assert_not_called()

    async def test_detach_false_invokes_foreground(self, config, mock_docker_client):
        mock_container = MagicMock()
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config)
        from unittest.mock import AsyncMock
        manager._run_foreground_container = AsyncMock()

        await manager.start(detach=False)

        mock_container.start.assert_called_once()
        manager._run_foreground_container.assert_called_once_with(mock_container)


# ---------------------------------------------------------------------------
# create_container — tty / stdin_open propagation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestCreateContainerOptions:
    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    def config(self):
        return DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
        )

    @pytest.fixture
    def mock_docker_client(self):
        with patch('mindor.core.foundation.containers.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    async def test_default_tty_stdin_open(self, config, mock_docker_client):
        mock_docker_client.containers.get.side_effect = NotFound("not found")

        manager = _runtime(config)
        await manager.create()

        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["tty"] is True
        assert call_args[1]["stdin_open"] is True

    async def test_tty_false_stdin_open_true(self, config, mock_docker_client):
        """Component manager uses tty=False to get demultiplexed stdout/stderr."""
        mock_docker_client.containers.get.side_effect = NotFound("not found")

        manager = _runtime(config)
        await manager.create(tty=False, stdin_open=True)

        call_args = mock_docker_client.containers.create.call_args
        assert call_args[1]["tty"] is False
        assert call_args[1]["stdin_open"] is True

    async def test_create_container_wraps_dockerexception(self, config, mock_docker_client):
        mock_docker_client.containers.get.side_effect = NotFound("not found")
        mock_docker_client.containers.create.side_effect = DockerException("daemon offline")

        manager = _runtime(config)

        with pytest.raises(RuntimeError, match="Failed to create container"):
            await manager.create()


# ---------------------------------------------------------------------------
# Error wrapping for the remaining container methods
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestContainerMethodErrorWrapping:
    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    def config(self):
        return DockerRuntimeConfig(
            type="docker",
            image="test-image:latest",
            container_name="test-container",
        )

    @pytest.fixture
    def mock_docker_client(self):
        with patch('mindor.core.foundation.containers.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    async def test_start_container_wraps_dockerexception(self, config, mock_docker_client):
        mock_docker_client.containers.get.side_effect = DockerException("daemon offline")

        manager = _runtime(config)
        with pytest.raises(RuntimeError, match="Failed to start container"):
            await manager.start(detach=True)

    async def test_stop_container_wraps_dockerexception(self, config, mock_docker_client):
        mock_container = MagicMock()
        mock_container.stop.side_effect = DockerException("daemon offline")
        mock_docker_client.containers.get.return_value = mock_container

        manager = _runtime(config)
        with pytest.raises(RuntimeError, match="Failed to stop container"):
            await manager.stop()

    async def test_is_container_running_wraps_dockerexception(self, config, mock_docker_client):
        mock_docker_client.containers.get.side_effect = DockerException("daemon offline")

        manager = _runtime(config)
        with pytest.raises(RuntimeError, match="Failed to check container"):
            await manager.is_running()

    async def test_exists_container_wraps_dockerexception(self, config, mock_docker_client):
        mock_docker_client.containers.get.side_effect = DockerException("daemon offline")

        manager = _runtime(config)
        with pytest.raises(RuntimeError, match="Failed to check container"):
            await manager.exists()


# ---------------------------------------------------------------------------
# DockerContainerRunner.__init__ — params may have None image / container_name
# ---------------------------------------------------------------------------

class TestRuntimeInitToleratesNone:
    @pytest.fixture
    def mock_docker_client(self):
        with patch('mindor.core.foundation.containers.docker.docker.from_env') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_init_accepts_none_image(self, mock_docker_client):
        """`DockerContainerRunner` does not validate params — that responsibility
        is delegated to the manager / DSL config layer."""
        params = DockerContainerParams(container_name="x")
        # Must not raise.
        DockerContainerRunner(params, verbose=False)

    def test_init_accepts_none_container_name(self, mock_docker_client):
        params = DockerContainerParams(image="test-image:latest")
        # Must not raise.
        DockerContainerRunner(params, verbose=False)


# ---------------------------------------------------------------------------
# DockerDeviceRequestsResolver
# ---------------------------------------------------------------------------

class TestDockerDeviceRequestsResolver:
    def test_none_returns_none(self):
        from mindor.core.foundation.containers.docker import DockerDeviceRequestsResolver
        assert DockerDeviceRequestsResolver(None).resolve() is None

    def test_all_uses_minus_one(self):
        from mindor.core.foundation.containers.docker import DockerDeviceRequestsResolver
        result = DockerDeviceRequestsResolver("all").resolve()
        assert len(result) == 1
        assert result[0]["Count"] == -1
        assert result[0]["Capabilities"] == [["gpu"]]

    def test_integer_count(self):
        from mindor.core.foundation.containers.docker import DockerDeviceRequestsResolver
        result = DockerDeviceRequestsResolver(2).resolve()
        assert result[0]["Count"] == 2

    def test_numeric_string_count(self):
        from mindor.core.foundation.containers.docker import DockerDeviceRequestsResolver
        result = DockerDeviceRequestsResolver("3").resolve()
        assert result[0]["Count"] == 3
