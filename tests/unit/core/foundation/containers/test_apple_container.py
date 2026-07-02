"""Tests for the Apple Container helpers in
`core.foundation.containers.apple_container`: Resolvers,
`AppleContainerImageBuilder`, and `AppleContainerRunner`."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindor.core.foundation.containers.apple_container import (
    AppleContainerImageBuilder,
    AppleContainerMount,
    AppleContainerMountsResolver,
    AppleContainerParams,
    AppleContainerPortsResolver,
    AppleContainerRunner,
)
from mindor.dsl.schema.containers.apple_container import (
    AppleContainerPortConfig,
    AppleContainerVolumeConfig,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _stub_container_cli_present():
    """Pretend the `container` CLI is installed so AppleContainerClient's
    __init__ preflight check passes on any host running the test suite."""
    with patch(
        "mindor.core.utils.containers.apple_container_client.shutil.which",
        return_value="/usr/local/bin/container",
    ):
        yield


def _mock_process(returncode: int = 0, stdout: bytes = b"") -> MagicMock:
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout, b""))
    return process


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------

class TestAppleContainerPortsResolver:
    def test_resolve_none(self):
        assert AppleContainerPortsResolver(None).resolve() == []

    def test_resolve_empty_list(self):
        assert AppleContainerPortsResolver([]).resolve() == []

    def test_resolve_int_port(self):
        assert AppleContainerPortsResolver([8080]).resolve() == ["8080:8080"]

    def test_resolve_string_port(self):
        assert AppleContainerPortsResolver(["80:8080"]).resolve() == ["80:8080"]

    def test_resolve_string_port_with_protocol(self):
        assert AppleContainerPortsResolver(["53:53/udp"]).resolve() == ["53:53/udp"]

    def test_resolve_port_config(self):
        config = AppleContainerPortConfig(container_port=8080, host_port=80)
        assert AppleContainerPortsResolver([config]).resolve() == ["80:8080/tcp"]

    def test_resolve_port_config_with_host_ip(self):
        config = AppleContainerPortConfig(container_port=8080, host_port=80, host_ip="127.0.0.1")
        assert AppleContainerPortsResolver([config]).resolve() == ["127.0.0.1:80:8080/tcp"]

    def test_resolve_multiple_mixed(self):
        result = AppleContainerPortsResolver([8080, "443:8443", 3000]).resolve()
        assert result == ["8080:8080", "443:8443", "3000:3000"]


class TestAppleContainerMountsResolver:
    def test_resolve_none(self):
        assert AppleContainerMountsResolver(None).resolve() == []

    def test_resolve_empty_list(self):
        assert AppleContainerMountsResolver([]).resolve() == []

    def test_resolve_string_named_volume(self):
        [mount] = AppleContainerMountsResolver(["data:/app/data"]).resolve()
        assert mount == AppleContainerMount(type="volume", source="data", target="/app/data")

    def test_resolve_string_bind(self):
        [mount] = AppleContainerMountsResolver(["/host/path:/in/container"]).resolve()
        assert mount == AppleContainerMount(type="bind", source="/host/path", target="/in/container")

    def test_resolve_string_readonly(self):
        [mount] = AppleContainerMountsResolver(["data:/app/data:ro"]).resolve()
        assert mount == AppleContainerMount(type="volume", source="data", target="/app/data", read_only=True)

    def test_resolve_volume_config_named(self):
        volume = AppleContainerVolumeConfig(name="my-vol", target="/data")
        [mount] = AppleContainerMountsResolver([volume]).resolve()
        assert mount == AppleContainerMount(type="volume", source="my-vol", target="/data")

    def test_resolve_volume_config_bind(self):
        volume = AppleContainerVolumeConfig(source="/host/path", target="/in/container")
        [mount] = AppleContainerMountsResolver([volume]).resolve()
        assert mount == AppleContainerMount(type="bind", source="/host/path", target="/in/container")

    def test_resolve_volume_config_explicit_type(self):
        volume = AppleContainerVolumeConfig(type="bind", source="rel-path", target="/x")
        [mount] = AppleContainerMountsResolver([volume]).resolve()
        assert mount == AppleContainerMount(type="bind", source="rel-path", target="/x")

    def test_resolve_volume_config_readonly(self):
        volume = AppleContainerVolumeConfig(name="cfg", target="/etc/app", read_only=True)
        [mount] = AppleContainerMountsResolver([volume]).resolve()
        assert mount == AppleContainerMount(type="volume", source="cfg", target="/etc/app", read_only=True)

    def test_resolve_multiple(self):
        result = AppleContainerMountsResolver([
            "data:/app/data",
            AppleContainerVolumeConfig(name="cfg", target="/etc/app"),
        ]).resolve()
        assert result == [
            AppleContainerMount(type="volume", source="data", target="/app/data"),
            AppleContainerMount(type="volume", source="cfg", target="/etc/app"),
        ]


# ---------------------------------------------------------------------------
# AppleContainerImageBuilder
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestAppleContainerImageBuilder:
    @pytest.fixture
    def builder_with_mock(self):
        builder = AppleContainerImageBuilder()
        builder._client = MagicMock()
        builder._client.run = AsyncMock(return_value=_mock_process())
        return builder

    async def test_build_minimal(self, builder_with_mock):
        await builder_with_mock.build("myapp:latest")

        builder_with_mock._client.run.assert_awaited_once()
        call_args = builder_with_mock._client.run.call_args
        assert call_args.args == ("build",)
        assert call_args.kwargs["args"] == ["-t", "myapp:latest", "."]
        assert call_args.kwargs["capture_output"] is False

    async def test_build_with_path(self, builder_with_mock):
        await builder_with_mock.build("myapp:latest", path="./ctx")

        call_args = builder_with_mock._client.run.call_args
        assert call_args.kwargs["args"] == ["-t", "myapp:latest", "./ctx"]

    async def test_build_with_dockerfile(self, builder_with_mock):
        await builder_with_mock.build(
            "myapp:latest",
            dockerfile="Dockerfile.prod",
            path="./ctx",
        )

        call_args = builder_with_mock._client.run.call_args
        assert call_args.kwargs["args"] == [
            "-t", "myapp:latest", "-f", "Dockerfile.prod", "./ctx",
        ]

    async def test_build_with_build_args(self, builder_with_mock):
        await builder_with_mock.build(
            "myapp:latest",
            build_args={"VERSION": "1.0", "ENV": "prod"},
        )

        call_args = builder_with_mock._client.run.call_args
        passed = call_args.kwargs["args"]
        assert "--build-arg" in passed
        assert "VERSION=1.0" in passed
        assert "ENV=prod" in passed

    async def test_build_without_tag(self, builder_with_mock):
        await builder_with_mock.build(None, path="./ctx")

        call_args = builder_with_mock._client.run.call_args
        # No -t when tag is None.
        assert "-t" not in call_args.kwargs["args"]

    async def test_pull(self, builder_with_mock):
        await builder_with_mock.pull("myapp:latest")

        call_args = builder_with_mock._client.run.call_args
        assert call_args.args == (["image", "pull"],)
        assert call_args.kwargs["args"] == ["myapp:latest"]

    async def test_remove(self, builder_with_mock):
        await builder_with_mock.remove("myapp:latest")

        call_args = builder_with_mock._client.run.call_args
        assert call_args.args == (["image", "rm"],)
        assert call_args.kwargs["args"] == ["myapp:latest"]

    async def test_remove_swallows_runtime_error(self, builder_with_mock):
        builder_with_mock._client.run = AsyncMock(side_effect=RuntimeError("missing"))
        # Must not raise.
        await builder_with_mock.remove("ghost:latest")

    async def test_exists_true(self, builder_with_mock):
        builder_with_mock._client.run = AsyncMock(
            return_value=_mock_process(stdout=b"myapp:latest\nother:1.0\n"),
        )
        assert await builder_with_mock.exists("myapp:latest") is True

    async def test_exists_false(self, builder_with_mock):
        builder_with_mock._client.run = AsyncMock(
            return_value=_mock_process(stdout=b"other:1.0\n"),
        )
        assert await builder_with_mock.exists("myapp:latest") is False

    async def test_exists_swallows_error(self, builder_with_mock):
        builder_with_mock._client.run = AsyncMock(side_effect=RuntimeError("daemon offline"))
        assert await builder_with_mock.exists("anything") is False


# ---------------------------------------------------------------------------
# AppleContainerRunner
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestAppleContainerRunner:
    def _runner(self, params: AppleContainerParams) -> AppleContainerRunner:
        runner = AppleContainerRunner(params)
        runner._client = MagicMock()
        runner._client.run = AsyncMock(return_value=_mock_process())
        return runner

    async def test_create_detached_minimal(self):
        params = AppleContainerParams(image="myapp:latest", container_name="c1")
        runner = self._runner(params)

        await runner.create()

        call_args = runner._client.run.call_args
        assert call_args.args == ("create",)
        passed = call_args.kwargs["args"]
        assert passed[:2] == ["--name", "c1"]
        assert passed[-1] == "myapp:latest"

    async def test_start_detached(self):
        params = AppleContainerParams(image="myapp:latest", container_name="c1")
        runner = self._runner(params)

        await runner.start(detach=True)

        call_args = runner._client.run.call_args
        assert call_args.args == ("start",)
        # No attach/interactive flags when detached.
        assert call_args.kwargs["args"] == ["c1"]

    async def test_start_foreground_runs_foreground_loop(self):
        params = AppleContainerParams(image="myapp:latest", container_name="c1")
        runner = self._runner(params)
        runner._run_foreground_container = AsyncMock()

        await runner.start(detach=False)

        runner._run_foreground_container.assert_awaited_once()
        # Foreground attaches stdout/stderr (-a) and stdin (-i).
        passed = runner._client.run.call_args.kwargs["args"]
        assert "-a" in passed and "-i" in passed

    async def test_create_includes_environment(self):
        params = AppleContainerParams(
            image="myapp:latest",
            container_name="c1",
            environment={"FOO": "bar"},
        )
        runner = self._runner(params)

        await runner.create()

        passed = runner._client.run.call_args.kwargs["args"]
        assert "-e" in passed
        assert "FOO=bar" in passed

    async def test_create_includes_cpus_and_mem(self):
        params = AppleContainerParams(
            image="myapp:latest",
            container_name="c1",
            cpus=2,
            mem_limit="1G",
        )
        runner = self._runner(params)

        await runner.create()

        passed = runner._client.run.call_args.kwargs["args"]
        assert "--cpus" in passed and "2" in passed
        assert "--memory" in passed and "1G" in passed

    async def test_create_appends_user_command_string(self):
        params = AppleContainerParams(
            image="myapp:latest",
            container_name="c1",
            command="echo hi",
        )
        runner = self._runner(params)

        await runner.create()

        passed = runner._client.run.call_args.kwargs["args"]
        assert passed[-1] == "echo hi"

    async def test_create_appends_user_command_list(self):
        params = AppleContainerParams(
            image="myapp:latest",
            container_name="c1",
            command=["sh", "-c", "echo hi"],
        )
        runner = self._runner(params)

        await runner.create()

        passed = runner._client.run.call_args.kwargs["args"]
        # Command tokens come after the image.
        assert passed[-3:] == ["sh", "-c", "echo hi"]

    async def test_stop(self):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))

        await runner.stop()

        call_args = runner._client.run.call_args
        assert call_args.args == ("stop",)
        assert call_args.kwargs["args"] == ["c1"]

    async def test_stop_logs_on_runtime_error(self, caplog):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))
        runner._client.run = AsyncMock(side_effect=RuntimeError("not running"))

        await runner.stop()  # must not raise

    async def test_remove_with_force(self):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))

        await runner.remove(force=True)

        call_args = runner._client.run.call_args
        assert call_args.args == ("rm",)
        assert call_args.kwargs["args"] == ["-f", "c1"]

    async def test_remove_without_force(self):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))

        await runner.remove()

        call_args = runner._client.run.call_args
        assert call_args.kwargs["args"] == ["c1"]

    async def test_is_running_true(self):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))
        runner._client.run = AsyncMock(return_value=_mock_process(stdout=b"c1\nc2\n"))

        assert await runner.is_running() is True

    async def test_is_running_false(self):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))
        runner._client.run = AsyncMock(return_value=_mock_process(stdout=b"c2\n"))

        assert await runner.is_running() is False

    async def test_exists_true(self):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))
        runner._client.run = AsyncMock(return_value=_mock_process(stdout=b"c1\n"))

        assert await runner.exists() is True

    async def test_exists_false(self):
        runner = self._runner(AppleContainerParams(image="x", container_name="c1"))
        runner._client.run = AsyncMock(return_value=_mock_process(stdout=b""))

        assert await runner.exists() is False

    async def test_create_pre_creates_named_volumes(self):
        runner = self._runner(AppleContainerParams(
            image="x",
            container_name="c1",
            volumes=[
                AppleContainerVolumeConfig(name="v1", target="/d1"),
                AppleContainerVolumeConfig(name="v2", target="/d2"),
            ],
        ))
        runner._client.run = AsyncMock(return_value=_mock_process())

        await runner.create()

        invocations = [
            (call.args[0], call.kwargs.get("args", []))
            for call in runner._client.run.await_args_list
        ]
        assert (["volume", "create"], ["v1"]) in invocations
        assert (["volume", "create"], ["v2"]) in invocations

    async def test_create_swallows_existing_named_volume(self):
        runner = self._runner(AppleContainerParams(
            image="x",
            container_name="c1",
            volumes=[AppleContainerVolumeConfig(name="v1", target="/d")],
        ))
        # `volume create` raises (already exists), `create` succeeds.
        async def fake_run(command, args=None, **kwargs):
            if command == ["volume", "create"]:
                raise RuntimeError("already exists")
            return _mock_process()
        runner._client.run = AsyncMock(side_effect=fake_run)

        await runner.create()  # must not raise
