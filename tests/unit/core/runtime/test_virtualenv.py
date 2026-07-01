"""Unit tests for `core/runtime/virtualenv.py` (lifecycle only).

Scope:
- `VirtualEnvRuntimeParams` carries driver/python/path/env/timeouts.
- `VirtualEnvRuntime` exposes pre-start state and path resolution helpers without
  actually creating a venv (which is exercised by integration tests).

End-to-end venv creation + worker spawn lives in
`tests/integration/core/component/runtime/test_component_virtualenv_runtime.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mindor.core.runtime.virtualenv import VirtualEnvRuntime, VirtualEnvRuntimeParams
from mindor.dsl.schema.runtime.impl.virtualenv import VirtualEnvDriver


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestVirtualEnvRuntimeParams:
    def test_default_values(self):
        params = VirtualEnvRuntimeParams()
        assert params.driver == VirtualEnvDriver.PYTHON
        assert params.python is None
        assert params.path is None
        assert params.env == {}
        assert params.start_timeout == 60.0
        assert params.stop_timeout == 30.0

    def test_custom_values(self):
        params = VirtualEnvRuntimeParams(
            driver=VirtualEnvDriver.PYENV,
            python="3.11.4",
            path=".venv/custom",
            env={"FOO": "bar"},
            start_timeout=120.0,
            stop_timeout=10.0,
        )
        assert params.driver == VirtualEnvDriver.PYENV
        assert params.python == "3.11.4"
        assert params.path == ".venv/custom"
        assert params.env == {"FOO": "bar"}
        assert params.start_timeout == 120.0
        assert params.stop_timeout == 10.0


class TestVirtualEnvRuntimePathResolution:
    def test_default_venv_path_under_cwd(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(worker_id="comp-1", worker_module="x", params=VirtualEnvRuntimeParams())
        expected = (tmp_path / ".runtime" / "components" / "comp-1" / "venv").resolve()
        assert runtime._venv_path == expected

    def test_custom_relative_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(
            worker_id="comp-2",
            worker_module="x",
            params=VirtualEnvRuntimeParams(path=".cache/myenv"),
        )
        assert runtime._venv_path == (tmp_path / ".cache" / "myenv").resolve()

    def test_venv_python_path_unix(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("os.name", "posix")
        runtime = VirtualEnvRuntime(worker_id="comp-3", worker_module="x", params=VirtualEnvRuntimeParams())
        assert runtime._venv_python() == runtime._venv_path / "bin" / "python"

    def test_venv_pip_path_unix(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("os.name", "posix")
        runtime = VirtualEnvRuntime(worker_id="comp-4", worker_module="x", params=VirtualEnvRuntimeParams())
        assert runtime._venv_pip() == runtime._venv_path / "bin" / "pip"


class TestVirtualEnvRuntimeEnvironment:
    def test_build_environment_includes_pythonunbuffered(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(worker_id="comp", worker_module="x", params=VirtualEnvRuntimeParams())
        env = runtime._build_environment(None)
        assert env["PYTHONUNBUFFERED"] == "1"

    def test_build_environment_applies_params_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(
            worker_id="comp",
            worker_module="x",
            params=VirtualEnvRuntimeParams(env={"FOO": "bar"}),
        )
        env = runtime._build_environment(None)
        assert env["FOO"] == "bar"

    def test_build_environment_overrides_win_over_params(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(
            worker_id="comp",
            worker_module="x",
            params=VirtualEnvRuntimeParams(env={"FOO": "from-params"}),
        )
        env = runtime._build_environment({"FOO": "from-overrides", "NEW": "value"})
        assert env["FOO"] == "from-overrides"
        assert env["NEW"] == "value"


class TestVirtualEnvRuntimeLifecycleState:
    @pytest.mark.anyio
    async def test_initial_state(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(worker_id="comp", worker_module="x", params=VirtualEnvRuntimeParams())
        assert runtime.subprocess is None
        assert runtime.is_alive is False

    @pytest.mark.anyio
    async def test_stop_is_safe_before_start(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(worker_id="comp", worker_module="x", params=VirtualEnvRuntimeParams())
        # Must not raise when the subprocess was never spawned.
        await runtime.stop()


class TestVirtualEnvRuntimeParamsValidation:
    @pytest.mark.anyio
    async def test_pyenv_driver_without_python_raises(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runtime = VirtualEnvRuntime(
            worker_id="comp",
            worker_module="x",
            params=VirtualEnvRuntimeParams(driver=VirtualEnvDriver.PYENV, python=None),
        )
        with pytest.raises(ValueError, match="must be set when driver is 'pyenv'"):
            runtime._ensure_venv()
