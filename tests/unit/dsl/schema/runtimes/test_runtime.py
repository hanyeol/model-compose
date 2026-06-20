"""Unit tests for the ``RuntimeConfig`` discriminated union.

Per-runtime-type tests live in their own files (``test_native.py``,
``test_embedded.py``, ``test_process.py``, ``test_docker.py``,
``test_apple_container.py``).
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from mindor.dsl.schema.runtime import RuntimeConfig
from mindor.dsl.schema.runtime.impl.apple_container import AppleContainerRuntimeConfig
from mindor.dsl.schema.runtime.impl.docker import DockerRuntimeConfig
from mindor.dsl.schema.runtime.impl.embedded import EmbeddedRuntimeConfig
from mindor.dsl.schema.runtime.impl.native import NativeRuntimeConfig
from mindor.dsl.schema.runtime.impl.process import ProcessRuntimeConfig
from mindor.dsl.schema.runtime.impl.types import RuntimeType


RuntimeAdapter = TypeAdapter(RuntimeConfig)


class TestDiscriminatorRouting:
    def test_native_routes_to_native_config(self):
        cfg = RuntimeAdapter.validate_python({"type": "native"})
        assert isinstance(cfg, NativeRuntimeConfig)
        assert cfg.type == RuntimeType.NATIVE

    def test_embedded_routes_to_embedded_config(self):
        cfg = RuntimeAdapter.validate_python({"type": "embedded"})
        assert isinstance(cfg, EmbeddedRuntimeConfig)

    def test_process_routes_to_process_config(self):
        cfg = RuntimeAdapter.validate_python({"type": "process"})
        assert isinstance(cfg, ProcessRuntimeConfig)

    def test_docker_routes_to_docker_config(self):
        cfg = RuntimeAdapter.validate_python({"type": "docker", "image": "python:3.11"})
        assert isinstance(cfg, DockerRuntimeConfig)

    def test_apple_container_routes_to_apple_container_config(self):
        cfg = RuntimeAdapter.validate_python({"type": "apple-container", "image": "python:3.11"})
        assert isinstance(cfg, AppleContainerRuntimeConfig)

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeAdapter.validate_python({"type": "unknown"})

    def test_missing_type_rejected(self):
        with pytest.raises(ValidationError):
            RuntimeAdapter.validate_python({})
