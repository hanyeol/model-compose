"""Smoke tests for the flattened ``controller/runtime`` package layout.

`native` and `apple_container` were collapsed from sub-packages into single
modules; `docker` keeps its sub-package because of the build context directory.
These tests just assert that each entry point still imports under both the
package path and the launcher symbol callers actually use.
"""

from __future__ import annotations


def test_specs_module_imports():
    from mindor.core.controller.runtime.base.specs import ControllerRuntimeSpecs

    assert ControllerRuntimeSpecs is not None


def test_native_launcher_imports():
    from mindor.core.controller.runtime.native import ControllerNativeRuntimeManager

    assert ControllerNativeRuntimeManager is not None


def test_apple_container_launcher_imports():
    from mindor.core.controller.runtime.apple_container import (
        ControllerAppleContainerRuntimeManager,
    )

    assert ControllerAppleContainerRuntimeManager is not None


def test_docker_launcher_imports():
    from mindor.core.controller.runtime.docker import ControllerDockerRuntimeManager

    assert ControllerDockerRuntimeManager is not None


def test_launchers_importable_from_controller_base():
    """`controller/base.py` pulls all three launchers; verify that path still works
    after flattening (regression guard for the relative import in apple_container)."""
    from mindor.core.controller.base import (
        ControllerNativeRuntimeManager,
        ControllerDockerRuntimeManager,
        ControllerAppleContainerRuntimeManager,
    )

    assert ControllerNativeRuntimeManager is not None
    assert ControllerDockerRuntimeManager is not None
    assert ControllerAppleContainerRuntimeManager is not None
