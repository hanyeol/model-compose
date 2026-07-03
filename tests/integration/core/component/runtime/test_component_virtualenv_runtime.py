"""Integration tests for the component virtualenv runtime.

These tests actually create a Python venv under a temporary directory, inject mindor + its
runtime requirements via pip, and round-trip a RUN message through a worker subprocess
launched on the venv's Python. They are slow (tens of seconds) but exercise the full
end-to-end path of the runtime.

Set the environment variable ``MINDOR_SKIP_VIRTUALENV_INTEGRATION=1`` to skip them locally.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.core.component.runtime.virtualenv import (
    ComponentVirtualEnvRuntimeManager,
)
from mindor.dsl.schema.action import ShellActionConfig
from mindor.dsl.schema.component.impl.shell import ShellComponentConfig
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig


pytestmark = pytest.mark.skipif(
    os.environ.get("MINDOR_SKIP_VIRTUALENV_INTEGRATION") == "1",
    reason="Virtualenv integration tests disabled via MINDOR_SKIP_VIRTUALENV_INTEGRATION=1",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def global_configs():
    return ComponentGlobalConfigs(
        components=[],
        listeners=[],
        gateways=[],
        workflows=[],
    )


@pytest.fixture
def venv_dir(tmp_path: Path) -> Path:
    """A clean working directory in which the manager will materialize its venv."""
    cwd = tmp_path / "workdir"
    cwd.mkdir()
    original_cwd = Path.cwd()
    os.chdir(cwd)
    try:
        yield cwd
    finally:
        os.chdir(original_cwd)


@pytest.mark.anyio
async def test_component_virtualenv_lifecycle(venv_dir: Path, global_configs):
    """End-to-end: create venv, inject mindor, run a shell echo action, stop."""
    config = ShellComponentConfig(
        id="venv-shell",
        type="shell",
        runtime=VirtualEnvRuntimeConfig(
            type="virtualenv",
            start_timeout="300s",
            stop_timeout="30s",
        ),
        actions=[
            ShellActionConfig(
                id="default",
                command=["echo", "hello from venv"],
                default=True,
            )
        ],
    )

    component = create_component("venv-shell", config, global_configs, daemon=False)

    await component.setup()  # should skip — virtualenv runtime
    await component.start()

    assert component._virtualenv_launcher is not None
    assert isinstance(component._virtualenv_launcher, ComponentVirtualEnvRuntimeManager)
    assert component._virtualenv_launcher._runtime.subprocess is not None
    assert component._virtualenv_launcher._runtime.subprocess.poll() is None

    # venv should be at .runtime/components/venv-shell/venv under the cwd.
    expected_venv = (venv_dir / ".runtime" / "components" / "venv-shell" / "venv").resolve()
    assert expected_venv.exists()
    assert (expected_venv / "bin" / "python").exists() or (
        expected_venv / "Scripts" / "python.exe"
    ).exists()

    # Worker subprocess must use the venv python, not the parent interpreter.
    worker_exe = component._virtualenv_launcher._runtime.subprocess.args[0]
    assert str(expected_venv) in worker_exe

    # mindor should have been copied into the venv's site-packages, not pip-installed.
    site_packages = component._virtualenv_launcher._runtime._venv_site_packages()
    assert (site_packages / "mindor" / "__init__.py").exists()

    import mindor.version
    version_file = site_packages / "mindor" / ".version"
    assert version_file.exists()
    assert version_file.read_text().strip() == mindor.version.__version__

    # Execute a round-trip RUN.
    result = await component.run(
        action_id="__default__",
        run_id="run-1",
        input={},
    )
    assert result is not None
    assert result["stdout"] == "hello from venv"
    assert result["exit_code"] == 0

    # Snapshot before stop — the launcher clears its `_runtime` handle on teardown.
    worker_subprocess = component._virtualenv_launcher._runtime.subprocess
    await component.stop()
    assert worker_subprocess.poll() is not None

    await component.teardown()


@pytest.mark.anyio
async def test_component_virtualenv_skips_injection_when_version_unchanged(
    venv_dir: Path, global_configs
):
    """When the host mindor version hasn't changed, the second start should reuse the
    existing venv & site-packages without rewriting mindor/."""
    config = ShellComponentConfig(
        id="venv-skip-injection",
        type="shell",
        runtime=VirtualEnvRuntimeConfig(
            type="virtualenv",
            start_timeout="300s",
            stop_timeout="30s",
        ),
        actions=[
            ShellActionConfig(
                id="default",
                command=["echo", "ok"],
                default=True,
            )
        ],
    )

    component = create_component("venv-skip-injection", config, global_configs, daemon=False)

    await component.setup()
    await component.start()
    # Snapshot the venv path before stop — the launcher clears its `_runtime` handle on teardown.
    site_packages = component._virtualenv_launcher._runtime._venv_site_packages()
    await component.stop()
    await component.teardown()

    # Touch a sentinel file inside mindor/ so we can verify it is not blown away on the
    # second start (which should skip reinjection because the version hasn't changed).
    sentinel = site_packages / "mindor" / "_test_sentinel.txt"
    sentinel.write_text("preserved")

    # Force-clear the component cache so create_component returns a fresh instance.
    from mindor.core.component.component import ComponentInstances
    ComponentInstances.pop("venv-skip-injection", None)
    component2 = create_component(
        "venv-skip-injection", config, global_configs, daemon=False
    )
    await component2.setup()
    await component2.start()

    assert sentinel.exists(), "unchanged version must preserve site-packages/mindor"

    # Ensure the reused venv still produces a working worker.
    result = await component2.run(action_id="__default__", run_id="run-2", input={})
    assert result["stdout"] == "ok"
    assert result["exit_code"] == 0

    await component2.stop()
    await component2.teardown()


def test_runtime_requirements_file_is_resolvable():
    """Sanity check that runtime requirements file lookup succeeds in both editable and
    installed layouts. Critical for venv injection to work."""
    from importlib.resources import files
    path = Path(str(files("mindor.core.runtime.bootstrap") / "requirements.txt"))
    assert path.exists(), f"Runtime requirements file not found at {path}"
    contents = path.read_text(encoding="utf-8")
    assert "click" in contents
    assert "pydantic" in contents
