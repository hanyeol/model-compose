"""Unit tests for ``LangfuseTracerConfig`` schema validation."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.tracer.impl.langfuse import LangfuseTracerConfig


class TestConnection:
    def test_url_only_ok(self):
        cfg = LangfuseTracerConfig(driver="langfuse", url="https://langfuse.example.com", public_key="pk", secret_key="sk")
        assert cfg.url == "https://langfuse.example.com"

    def test_host_only_ok(self):
        cfg = LangfuseTracerConfig(driver="langfuse", host="langfuse.internal", public_key="pk", secret_key="sk")
        assert cfg.host == "langfuse.internal"

    def test_url_and_host_together_rejected(self):
        with pytest.raises(ValidationError, match="Either 'url' or 'host'"):
            LangfuseTracerConfig(
                driver="langfuse", url="https://x", host="y",
                public_key="pk", secret_key="sk",
            )

    def test_default_host_when_neither_provided(self):
        cfg = LangfuseTracerConfig(driver="langfuse", public_key="pk", secret_key="sk")
        assert cfg.host == "cloud.langfuse.com"
