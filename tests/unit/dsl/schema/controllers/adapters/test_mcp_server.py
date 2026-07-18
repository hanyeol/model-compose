"""Unit tests for ``McpServerControllerAdapterConfig`` schema validation."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.controller.adapter.impl.mcp_server import (
    McpServerControllerAdapterConfig,
    McpServerTransport,
)


class TestTransport:
    """``transport`` selects between streamable HTTP (default) and stdio."""

    def test_defaults_to_http(self):
        cfg = McpServerControllerAdapterConfig.model_validate({"type": "mcp-server"})
        assert cfg.transport == McpServerTransport.HTTP

    def test_accepts_http_string(self):
        cfg = McpServerControllerAdapterConfig.model_validate({
            "type": "mcp-server", "transport": "http",
        })
        assert cfg.transport == McpServerTransport.HTTP

    def test_accepts_stdio_string(self):
        cfg = McpServerControllerAdapterConfig.model_validate({
            "type": "mcp-server", "transport": "stdio",
        })
        assert cfg.transport == McpServerTransport.STDIO

    def test_rejects_unknown_transport(self):
        with pytest.raises(ValidationError):
            McpServerControllerAdapterConfig.model_validate({
                "type": "mcp-server", "transport": "grpc",
            })
