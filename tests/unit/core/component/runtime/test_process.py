"""Unit tests for `component/runtime/process.py`.

Scope:
- `ProcessRuntimeConfig` (DSL schema) accepts expected fields with sane defaults.
- `ComponentProcessRuntimeLauncher` converts the DSL config into `ProcessRuntimeParams`
  and exposes its pre-start state.
- `ComponentProcessRuntimeWorker` initializes correctly.

End-to-end lifecycle / round-trip behavior (RUN, RESULT, STREAM_*) lives in the
integration test suite (`tests/integration/core/component/runtime/...`,
`tests/integration/core/runtime/test_ipc_stream_roundtrip.py`).
"""

from __future__ import annotations

from multiprocessing import Queue

import pytest

from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.process import (
    ComponentProcessRuntimeLauncher,
    ComponentProcessRuntimeWorker,
)
from mindor.core.runtime.process import ProcessRuntimeParams
from mindor.dsl.schema.component.impl.shell import ShellComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig, EmbeddedRuntimeConfig
from mindor.dsl.schema.runtime.impl.process import IpcMethod


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def global_configs():
    return ComponentGlobalConfigs(components=[], listeners=[], gateways=[], workflows=[])


# ---------------------------------------------------------------------------
# DSL schema
# ---------------------------------------------------------------------------

class TestProcessRuntimeConfig:
    def test_defaults(self):
        config = ProcessRuntimeConfig(type="process")
        assert config.type == "process"
        assert config.env == {}
        assert config.working_dir is None
        assert config.start_timeout == "60s"
        assert config.stop_timeout == "30s"
        assert config.ipc_method == IpcMethod.QUEUE
        assert config.socket_path is None
        assert config.pipe_name is None
        assert config.tcp_port is None
        assert config.max_memory is None
        assert config.cpu_limit is None

    def test_env(self):
        config = ProcessRuntimeConfig(type="process", env={"FOO": "bar", "BAZ": "qux"})
        assert config.env == {"FOO": "bar", "BAZ": "qux"}

    def test_custom_timeouts(self):
        config = ProcessRuntimeConfig(type="process", start_timeout="2m", stop_timeout="10s")
        assert config.start_timeout == "2m"
        assert config.stop_timeout == "10s"

    def test_working_directory(self):
        config = ProcessRuntimeConfig(type="process", working_dir="/app/workspace")
        assert config.working_dir == "/app/workspace"

    @pytest.mark.parametrize(
        "method, extra",
        [
            (IpcMethod.QUEUE, {}),
            (IpcMethod.UNIX_SOCKET, {"socket_path": "/tmp/m.sock"}),
            (IpcMethod.NAMED_PIPE, {"pipe_name": r"\\.\pipe\m"}),
            (IpcMethod.TCP_SOCKET, {"tcp_port": 9000}),
        ],
    )
    def test_ipc_methods(self, method, extra):
        config = ProcessRuntimeConfig(type="process", ipc_method=method, **extra)
        assert config.ipc_method == method
        for key, value in extra.items():
            assert getattr(config, key) == value

    def test_resource_limits(self):
        config = ProcessRuntimeConfig(type="process", max_memory="2g", cpu_limit=2.5)
        assert config.max_memory == "2g"
        assert config.cpu_limit == 2.5


class TestEmbeddedRuntimeConfig:
    def test_minimal_config(self):
        config = EmbeddedRuntimeConfig(type="embedded")
        assert config.type == "embedded"


# ---------------------------------------------------------------------------
# ComponentProcessRuntimeLauncher (pre-start state only)
# ---------------------------------------------------------------------------

class TestComponentProcessRuntimeLauncher:
    def _make_config(self, **runtime_overrides):
        return ShellComponentConfig(
            id="test-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process", **runtime_overrides),
            command=["echo", "test"],
        )

    def test_basic_initialization(self, global_configs):
        config = self._make_config()
        launcher = ComponentProcessRuntimeLauncher("test-shell", config, global_configs)

        assert launcher.worker_id == "test-shell"
        assert launcher.component_config is config
        assert launcher.global_configs is global_configs
        assert isinstance(launcher.params, ProcessRuntimeParams)

    def test_params_converted_from_config(self, global_configs):
        config = self._make_config(
            env={"TEST_VAR": "value"},
            start_timeout="2m",
            stop_timeout="10s",
        )
        launcher = ComponentProcessRuntimeLauncher("test-shell", config, global_configs)

        assert launcher.params.env == {"TEST_VAR": "value"}
        assert launcher.params.start_timeout == 120.0   # 2m → 120s
        assert launcher.params.stop_timeout == 10.0

    def test_pre_start_state(self, global_configs):
        config = self._make_config()
        launcher = ComponentProcessRuntimeLauncher("test-shell", config, global_configs)

        # Composition: no proxy / runtime / queues until start()
        assert launcher._proxy is None
        assert launcher._channel is None
        assert launcher._runtime is None
        assert launcher._request_queue is None
        assert launcher._response_queue is None

    def test_default_timeouts(self, global_configs):
        config = self._make_config()
        launcher = ComponentProcessRuntimeLauncher("test-shell", config, global_configs)
        assert launcher.params.start_timeout == 60.0
        assert launcher.params.stop_timeout == 30.0


# ---------------------------------------------------------------------------
# ComponentProcessRuntimeWorker
# ---------------------------------------------------------------------------

class TestComponentProcessRuntimeWorker:
    def test_initialization(self, global_configs):
        config = ShellComponentConfig(
            id="w",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=["echo", "x"],
        )
        request_queue = Queue()
        response_queue = Queue()

        worker = ComponentProcessRuntimeWorker(
            "w", config, global_configs, request_queue, response_queue,
        )

        assert worker.worker_id == "w"
        assert worker.component_config is config
        assert worker.global_configs is global_configs
        assert worker.request_queue is request_queue
        assert worker.response_queue is response_queue
        assert worker.component is None
        assert worker.running is True
