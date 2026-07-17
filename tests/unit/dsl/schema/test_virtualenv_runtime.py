"""Schema-level tests for the virtualenv runtime config."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from mindor.dsl.schema.runtime import RuntimeConfig, RuntimeType
from mindor.dsl.schema.runtime.impl.virtualenv import (
    VirtualEnvRuntimeConfig,
    VirtualEnvDriver,
)
from mindor.dsl.schema.controller import ControllerConfig


class TestVirtualEnvRuntimeConfig:
    def test_defaults(self):
        adapter = TypeAdapter(RuntimeConfig)
        cfg = adapter.validate_python({"type": "virtualenv"})

        assert isinstance(cfg, VirtualEnvRuntimeConfig)
        assert cfg.type == RuntimeType.VIRTUALENV
        assert cfg.driver == VirtualEnvDriver.PYTHON
        assert cfg.path is None
        assert cfg.python is None

    def test_custom_pyenv(self):
        adapter = TypeAdapter(RuntimeConfig)
        cfg = adapter.validate_python({
            "type": "virtualenv",
            "driver": "pyenv",
            "python": "3.12.0",
            "path": ".venv-x",
        })

        assert cfg.driver == VirtualEnvDriver.PYENV
        assert cfg.python == "3.12.0"
        assert cfg.path == ".venv-x"


class TestControllerValidateRuntime:
    def test_rejects_virtualenv(self):
        with pytest.raises(ValidationError) as exc:
            ControllerConfig(runtime={"type": "virtualenv"}, adapters=[])

        message = str(exc.value)
        assert "virtualenv" in message

    def test_accepts_native(self):
        cfg = ControllerConfig(runtime={"type": "native"}, adapters=[])
        assert cfg.runtime.type == RuntimeType.NATIVE
