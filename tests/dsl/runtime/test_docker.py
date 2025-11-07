import pytest
from mindor.dsl.schema.runtime.impl.docker import (
    DockerRuntimeConfig,
    DockerBuildConfig,
    DockerPortConfig,
    DockerVolumeConfig,
    DockerHealthCheck,
)


class TestDockerBuildConfig:
    """Test DockerBuildConfig schema"""

    def test_minimal_build_config(self):
        """Test minimal build configuration"""
        config = DockerBuildConfig()

        assert config.context is None
        assert config.dockerfile is None
        assert config.args is None
        assert config.target is None

    def test_full_build_config(self):
        """Test full build configuration"""
        config = DockerBuildConfig(
            context="./docker",
            dockerfile="Dockerfile.prod",
            args={"BUILD_ENV": "production", "VERSION": "1.0.0" },
            target="production",
            cache_from=["myapp:latest"],
            labels={"maintainer": "team@example.com" },
            network="host",
            pull=True,
            shm_size="2g",
        )

        assert config.context == "./docker"
        assert config.dockerfile == "Dockerfile.prod"
        assert config.args == { "BUILD_ENV": "production", "VERSION": "1.0.0" }
        assert config.target == "production"
        assert config.cache_from == ["myapp:latest"]
        assert config.labels == { "maintainer": "team@example.com" }
        assert config.network == "host"
        assert config.pull is True
        assert config.shm_size == "2g"


class TestDockerPortConfig:
    """Test DockerPortConfig schema"""

    def test_minimal_port_config(self):
        """Test minimal port configuration with only target port"""
        config = DockerPortConfig(target=8080)

        assert config.target == 8080
        assert config.published is None
        assert config.protocol == "tcp"
        assert config.mode is None

    def test_full_port_config(self):
        """Test full port configuration"""
        config = DockerPortConfig(
            target=8080,
            published=80,
            protocol="tcp",
            mode="ingress"
        )

        assert config.target == 8080
        assert config.published == 80
        assert config.protocol == "tcp"
        assert config.mode == "ingress"

    def test_udp_protocol(self):
        """Test UDP protocol configuration"""
        config = DockerPortConfig(target=53, protocol="udp")

        assert config.target == 53
        assert config.protocol == "udp"


class TestDockerVolumeConfig:
    """Test DockerVolumeConfig schema"""

    def test_bind_mount(self):
        """Test bind mount configuration"""
        config = DockerVolumeConfig(
            type="bind",
            source="/host/path",
            target="/container/path",
            read_only=True
        )

        assert config.type == "bind"
        assert config.source == "/host/path"
        assert config.target == "/container/path"
        assert config.read_only is True

    def test_named_volume(self):
        """Test named volume configuration"""
        config = DockerVolumeConfig(
            type="volume",
            source="my-volume",
            target="/data",
            volume={"nocopy": "true" }
        )

        assert config.type == "volume"
        assert config.source == "my-volume"
        assert config.target == "/data"
        assert config.volume == { "nocopy": "true" }

    def test_tmpfs_mount(self):
        """Test tmpfs mount configuration"""
        config = DockerVolumeConfig(
            type="tmpfs",
            target="/tmp",
            tmpfs={"size": "100m" }
        )

        assert config.type == "tmpfs"
        assert config.target == "/tmp"
        assert config.tmpfs == { "size": "100m" }


class TestDockerHealthCheck:
    """Test DockerHealthCheck schema"""

    def test_minimal_healthcheck(self):
        """Test minimal healthcheck with defaults"""
        config = DockerHealthCheck(test="curl -f http://localhost/health")

        assert config.test == "curl -f http://localhost/health"
        assert config.interval == "30s"
        assert config.timeout == "30s"
        assert config.max_retry_count == 3
        assert config.start_period == "0s"

    def test_healthcheck_with_list_command(self):
        """Test healthcheck with command as list"""
        config = DockerHealthCheck(
            test=[ "CMD-SHELL", "curl -f http://localhost/health || exit 1" ]
        )

        assert config.test == [ "CMD-SHELL", "curl -f http://localhost/health || exit 1" ]

    def test_full_healthcheck(self):
        """Test full healthcheck configuration"""
        config = DockerHealthCheck(
            test="curl -f http://localhost/health",
            interval="10s",
            timeout="5s",
            max_retry_count=5,
            start_period="30s"
        )

        assert config.test == "curl -f http://localhost/health"
        assert config.interval == "10s"
        assert config.timeout == "5s"
        assert config.max_retry_count == 5
        assert config.start_period == "30s"


class TestDockerRuntimeConfig:
    """Test DockerRuntimeConfig schema"""

    def test_minimal_config_with_image(self):
        """Test minimal configuration with image"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest"
        )

        assert config.type == "docker"
        assert config.image == "nginx:latest"
        assert config.build is None
        assert config.restart == "no"

    def test_config_with_build(self):
        """Test configuration with build settings"""
        config = DockerRuntimeConfig(
            type="docker",
            build=DockerBuildConfig(
                context=".",
                dockerfile="Dockerfile"
            )
        )

        assert config.type == "docker"
        assert config.build is not None
        assert config.build.context == "."
        assert config.build.dockerfile == "Dockerfile"

    def test_port_configurations(self):
        """Test various port configuration formats"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            ports=[
                8080,  # Simple int
                "9090:8080",  # String format
                DockerPortConfig(target=3000, published=80)  # Object format
            ]
        )

        assert len(config.ports) == 3
        assert config.ports[0] == 8080
        assert config.ports[1] == "9090:8080"
        assert isinstance(config.ports[2], DockerPortConfig)

    def test_volume_configurations(self):
        """Test various volume configuration formats"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            volumes=[
                "/host:/container",  # Simple string
                DockerVolumeConfig(
                    type="bind",
                    source="/data",
                    target="/app/data"
                )
            ]
        )

        assert len(config.volumes) == 2
        assert config.volumes[0] == "/host:/container"
        assert isinstance(config.volumes[1], DockerVolumeConfig)

    def test_environment_variables(self):
        """Test environment variable configuration"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            environment={
                "ENV": "production",
                "DEBUG": False,
                "PORT": 8080,
                "TIMEOUT": 30.5
            }
        )

        assert config.environment["ENV"] == "production"
        assert config.environment["DEBUG"] is False
        assert config.environment["PORT"] == 8080
        assert config.environment["TIMEOUT"] == 30.5

    def test_env_file_string(self):
        """Test env_file as string"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            env_file=".env"
        )

        assert config.env_file == ".env"

    def test_env_file_list(self):
        """Test env_file as list"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            env_file=[ ".env", ".env.production" ]
        )

        assert config.env_file == [ ".env", ".env.production" ]

    def test_command_string(self):
        """Test command as string"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            command="python app.py"
        )

        assert config.command == "python app.py"

    def test_command_list(self):
        """Test command as list"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            command=[ "python", "app.py", "--port", "8080" ]
        )

        assert config.command == [ "python", "app.py", "--port", "8080" ]

    def test_resource_limits(self):
        """Test resource limit configuration"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            mem_limit="512m",
            memswap_limit="1g",
            cpus="1.5",
            cpu_shares=512
        )

        assert config.mem_limit == "512m"
        assert config.memswap_limit == "1g"
        assert config.cpus == "1.5"
        assert config.cpu_shares == 512

    def test_restart_policies(self):
        """Test all restart policies"""
        for policy in [ "no", "always", "on-failure", "unless-stopped" ]:
            config = DockerRuntimeConfig(
                type="docker",
                image="nginx:latest",
                restart=policy
            )
            assert config.restart == policy

    def test_full_configuration(self):
        """Test comprehensive configuration"""
        config = DockerRuntimeConfig(
            type="docker",
            image="myapp:latest",
            build=DockerBuildConfig(
                context=".",
                dockerfile="Dockerfile",
                args={"VERSION": "1.0.0" }
            ),
            container_name="myapp-container",
            hostname="myapp",
            ports=[ 8080, "9090:8080" ],
            networks=[ "frontend", "backend" ],
            volumes=[ "/data:/app/data" ],
            environment={ "ENV": "production" },
            env_file=".env",
            command=[ "python", "app.py" ],
            entrypoint=[ "/entrypoint.sh" ],
            working_dir="/app",
            user="appuser",
            mem_limit="1g",
            cpus="2.0",
            restart="unless-stopped",
            healthcheck=DockerHealthCheck(
                test="curl -f http://localhost/health"
            ),
            labels={ "app": "myapp" },
            privileged=False,
            security_opt=["no-new-privileges"]
        )

        assert config.type == "docker"
        assert config.image == "myapp:latest"
        assert config.container_name == "myapp-container"
        assert config.hostname == "myapp"
        assert len(config.ports) == 2
        assert len(config.networks) == 2
        assert len(config.volumes) == 1
        assert config.environment["ENV"] == "production"
        assert config.restart == "unless-stopped"
        assert config.healthcheck is not None
        assert config.privileged is False

    def test_networks_default(self):
        """Test networks defaults to empty list"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest"
        )

        assert config.networks == []

    def test_logging_configuration(self):
        """Test logging configuration"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            logging={
                "driver": "json-file",
                "options": {
                    "max-size": "10m",
                    "max-file": "3"
                }
            }
        )

        assert config.logging["driver"] == "json-file"
        assert config.logging["options"]["max-size"] == "10m"

    def test_security_options(self):
        """Test security options"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            security_opt=[
                "no-new-privileges",
                "seccomp=unconfined"
            ]
        )

        assert len(config.security_opt) == 2
        assert "no-new-privileges" in config.security_opt


class TestDockerRuntimeConfigValidation:
    """Test DockerRuntimeConfig validation scenarios"""

    def test_missing_image_and_build(self):
        """Test that config can be created without image or build (they're optional)"""
        config = DockerRuntimeConfig(type="docker")

        assert config.image is None
        assert config.build is None

    def test_cpus_as_float(self):
        """Test cpus can be float"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            cpus=1.5
        )

        assert config.cpus == 1.5

    def test_cpus_as_string(self):
        """Test cpus can be string"""
        config = DockerRuntimeConfig(
            type="docker",
            image="nginx:latest",
            cpus="1.5"
        )

        assert config.cpus == "1.5"
