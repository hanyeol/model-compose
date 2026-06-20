"""Unit tests for ``NativeRuntimeConfig``."""

from mindor.dsl.schema.runtime.impl.native import NativeRuntimeConfig
from mindor.dsl.schema.runtime.impl.types import RuntimeType


class TestNativeRuntimeConfig:
    def test_minimal(self):
        cfg = NativeRuntimeConfig(type="native")
        assert cfg.type == RuntimeType.NATIVE
