"""Unit tests for `component/runtime/virtualenv.py`.

Scope:
- `VirtualEnvRuntimeConfig` (DSL schema) accepts expected fields with sane defaults.
- `ComponentVirtualEnvRuntimeManager` converts the DSL config into
  `VirtualEnvRuntimeParams` and exposes pre-start state.
- `ComponentVirtualEnvRuntimeWorker` initializes correctly.

End-to-end venv creation + worker spawn lives in
`tests/integration/core/component/runtime/test_component_virtualenv_runtime.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.virtualenv import (
    ComponentVirtualEnvRuntimeManager,
    ComponentVirtualEnvRuntimeWorker,
)
from mindor.core.runtime.virtualenv import VirtualEnvRuntimeParams
from mindor.dsl.schema.action import ShellActionConfig
from mindor.dsl.schema.component.impl.shell import ShellComponentConfig
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def global_configs():
    return ComponentGlobalConfigs(components=[], listeners=[], gateways=[], workflows=[])


# ---------------------------------------------------------------------------
# DSL schema
# ---------------------------------------------------------------------------

class TestVirtualEnvRuntimeConfig:
    def test_defaults(self):
        config = VirtualEnvRuntimeConfig(type="virtualenv")
        assert config.type == "virtualenv"
        assert config.driver == VirtualEnvDriver.PYTHON
        assert config.path is None
        assert config.python is None
        assert config.env == {}
        assert config.start_timeout == "60s"
        assert config.stop_timeout == "30s"

    def test_pyenv_driver_with_python(self):
        config = VirtualEnvRuntimeConfig(
            type="virtualenv",
            driver=VirtualEnvDriver.PYENV,
            python="3.11.4",
        )
        assert config.driver == VirtualEnvDriver.PYENV
        assert config.python == "3.11.4"

    def test_custom_path_and_env(self):
        config = VirtualEnvRuntimeConfig(
            type="virtualenv",
            path=".venv/custom",
            env={"FOO": "bar"},
        )
        assert config.path == ".venv/custom"
        assert config.env == {"FOO": "bar"}

    def test_custom_timeouts(self):
        config = VirtualEnvRuntimeConfig(
            type="virtualenv",
            start_timeout="3m",
            stop_timeout="15s",
        )
        assert config.start_timeout == "3m"
        assert config.stop_timeout == "15s"


# ---------------------------------------------------------------------------
# ComponentVirtualEnvRuntimeManager (pre-start state only)
# ---------------------------------------------------------------------------

class TestComponentVirtualEnvRuntimeManager:
    def _make_config(self, **runtime_overrides):
        return ShellComponentConfig(
            id="venv-shell",
            type="shell",
            runtime=VirtualEnvRuntimeConfig(type="virtualenv", **runtime_overrides),
            actions=[
                ShellActionConfig(id="default", command=["echo", "hi"], default=True)
            ],
        )

    def test_basic_initialization(self, global_configs):
        config = self._make_config()
        launcher = ComponentVirtualEnvRuntimeManager("venv-shell", config, global_configs)

        assert launcher.worker_id == "venv-shell"
        assert launcher.component_config is config
        assert launcher.global_configs is global_configs
        assert isinstance(launcher.params, VirtualEnvRuntimeParams)

    def test_params_converted_from_config(self, global_configs):
        config = self._make_config(
            driver=VirtualEnvDriver.PYENV,
            python="3.11.4",
            path=".venv/custom",
            env={"FOO": "bar"},
            start_timeout="3m",
            stop_timeout="15s",
        )
        launcher = ComponentVirtualEnvRuntimeManager("venv-shell", config, global_configs)

        assert launcher.params.driver == VirtualEnvDriver.PYENV
        assert launcher.params.python == "3.11.4"
        assert launcher.params.path == ".venv/custom"
        assert launcher.params.env == {"FOO": "bar"}
        assert launcher.params.start_timeout == 180.0  # 3m → 180s
        assert launcher.params.stop_timeout == 15.0

    def test_pre_start_state(self, global_configs):
        config = self._make_config()
        launcher = ComponentVirtualEnvRuntimeManager("venv-shell", config, global_configs)

        # Composition: nothing materialized until start()
        assert launcher._proxy is None
        assert launcher._channel is None
        assert launcher._runtime is None

    def test_default_timeouts(self, global_configs):
        config = self._make_config()
        launcher = ComponentVirtualEnvRuntimeManager("venv-shell", config, global_configs)
        assert launcher.params.start_timeout == 60.0
        assert launcher.params.stop_timeout == 30.0

# ---------------------------------------------------------------------------
# ComponentVirtualEnvRuntimeWorker
# ---------------------------------------------------------------------------

class TestComponentVirtualEnvRuntimeWorker:
    def test_initialization(self, global_configs):
        config = ShellComponentConfig(
            id="w",
            type="shell",
            runtime=VirtualEnvRuntimeConfig(type="virtualenv"),
            command=["echo", "x"],
        )

        # The worker's channel is a SubprocessPipeChannel in production, but here
        # we just verify the constructor wires arguments through.
        sentinel_channel = object()
        worker = ComponentVirtualEnvRuntimeWorker(
            "w", config, global_configs, sentinel_channel,  # type: ignore[arg-type]
        )

        assert worker.worker_id == "w"
        assert worker.component_config is config
        assert worker.global_configs is global_configs
        assert worker.channel is sentinel_channel
        assert worker.component is None
        assert worker.running is True
