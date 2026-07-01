"""Unit tests for ``AppleContainerRuntimeConfig`` and its nested config models."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.runtime.impl.apple_container import AppleContainerRuntimeConfig
from mindor.dsl.schema.containers.apple_container import (
    AppleContainerBuildConfig,
    AppleContainerHealthCheck,
    AppleContainerVolumeConfig,
)


class TestAppleContainerBuildConfig:
    def test_minimal(self):
        cfg = AppleContainerBuildConfig()
        assert cfg.context is None
        assert cfg.dockerfile is None
        assert cfg.args is None

    def test_with_args(self):
        cfg = AppleContainerBuildConfig(
            context="./docker", dockerfile="Dockerfile",
            args={"VERSION": "1.0", "DEBUG": True, "PORT": 8080},
        )
        assert cfg.context == "./docker"
        assert cfg.args["VERSION"] == "1.0"
        assert cfg.args["DEBUG"] is True
        assert cfg.args["PORT"] == 8080


class TestAppleContainerVolumeConfig:
    def test_required_fields(self):
        cfg = AppleContainerVolumeConfig(name="data-vol", target="/data")
        assert cfg.name == "data-vol"
        assert cfg.target == "/data"
        assert cfg.read_only is None

    def test_read_only_flag(self):
        cfg = AppleContainerVolumeConfig(name="cfg-vol", target="/etc/cfg", read_only=True)
        assert cfg.read_only is True

    def test_bind_source(self):
        cfg = AppleContainerVolumeConfig(source="/host/data", target="/data")
        assert cfg.source == "/host/data"
        assert cfg.name is None

    def test_explicit_type(self):
        cfg = AppleContainerVolumeConfig(type="bind", source="/host/data", target="/data")
        assert cfg.type == "bind"

    def test_missing_target_rejected(self):
        with pytest.raises(ValidationError):
            AppleContainerVolumeConfig(name="vol")


class TestAppleContainerHealthCheck:
    def test_minimal_defaults(self):
        cfg = AppleContainerHealthCheck(test="curl localhost/health")
        assert cfg.test == "curl localhost/health"
        assert cfg.interval == "30s"
        assert cfg.timeout == "30s"
        assert cfg.max_retry_count == 3
        assert cfg.start_period == "0s"

    def test_test_as_list(self):
        cfg = AppleContainerHealthCheck(test=["CMD", "curl", "localhost"])
        assert cfg.test == ["CMD", "curl", "localhost"]

    def test_missing_test_rejected(self):
        with pytest.raises(ValidationError):
            AppleContainerHealthCheck()


class TestAppleContainerRuntimeConfig:
    def test_minimal(self):
        cfg = AppleContainerRuntimeConfig(type="apple-container")
        assert cfg.image is None
        assert cfg.build is None
        assert cfg.ports is None
        assert cfg.volumes is None
        assert cfg.environment is None

    def test_with_image(self):
        cfg = AppleContainerRuntimeConfig(type="apple-container", image="nginx:1.25")
        assert cfg.image == "nginx:1.25"

    def test_with_config(self):
        cfg = AppleContainerRuntimeConfig(
            type="apple-container",
            build={"context": "./app", "dockerfile": "Dockerfile"},
        )
        assert isinstance(cfg.build, AppleContainerBuildConfig)
        assert cfg.build.context == "./app"

    def test_with_ports_mixed_int_and_string(self):
        cfg = AppleContainerRuntimeConfig(type="apple-container", ports=["8080:80", 9000])
        assert cfg.ports == ["8080:80", 9000]

    def test_volumes_accepts_strings_and_objects(self):
        cfg = AppleContainerRuntimeConfig(
            type="apple-container",
            volumes=[
                "host-vol:/container/path",
                {"name": "data", "target": "/data"},
            ],
        )
        assert len(cfg.volumes) == 2
        assert cfg.volumes[0] == "host-vol:/container/path"
        assert isinstance(cfg.volumes[1], AppleContainerVolumeConfig)
        assert cfg.volumes[1].name == "data"

    def test_environment_accepts_mixed_types(self):
        cfg = AppleContainerRuntimeConfig(
            type="apple-container",
            environment={"STR": "v", "INT": 42, "FLOAT": 1.5, "BOOL": True},
        )
        assert cfg.environment["STR"] == "v"
        assert cfg.environment["INT"] == 42
        assert cfg.environment["BOOL"] is True

    def test_command_as_string_or_list(self):
        cfg1 = AppleContainerRuntimeConfig(type="apple-container", command="python main.py")
        cfg2 = AppleContainerRuntimeConfig(type="apple-container", command=["python", "main.py"])
        assert cfg1.command == "python main.py"
        assert cfg2.command == ["python", "main.py"]

    def test_resource_limits(self):
        cfg = AppleContainerRuntimeConfig(
            type="apple-container", cpus=2.0, mem_limit="4G",
        )
        assert cfg.cpus == 2.0
        assert cfg.mem_limit == "4G"

    def test_healthcheck(self):
        cfg = AppleContainerRuntimeConfig(
            type="apple-container",
            healthcheck={"test": "curl localhost"},
        )
        assert isinstance(cfg.healthcheck, AppleContainerHealthCheck)
        assert cfg.healthcheck.test == "curl localhost"

    def test_labels(self):
        cfg = AppleContainerRuntimeConfig(
            type="apple-container", labels={"env": "prod", "team": "core"},
        )
        assert cfg.labels == {"env": "prod", "team": "core"}
