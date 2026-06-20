"""Unit tests for ``EmbeddedRuntimeConfig``."""

from mindor.dsl.schema.runtime.impl.embedded import EmbeddedRuntimeConfig
from mindor.dsl.schema.runtime.impl.types import RuntimeType


class TestEmbeddedRuntimeConfig:
    def test_minimal(self):
        cfg = EmbeddedRuntimeConfig(type="embedded")
        assert cfg.type == RuntimeType.EMBEDDED
