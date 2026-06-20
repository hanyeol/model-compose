"""Unit tests for ``HttpServerControllerAdapterConfig`` schema validation."""

from mindor.dsl.schema.controller.adapter.impl.http_server import (
    HttpServerControllerAdapterConfig,
    WebSocketConfig,
)


class TestWebSocket:
    """``websocket`` accepts ``True`` (default config), ``False`` (disabled),
    or a config object."""

    def test_websocket_true_inflated_to_default_config(self):
        cfg = HttpServerControllerAdapterConfig.model_validate({
            "type": "http-server", "websocket": True,
        })
        assert isinstance(cfg.websocket, WebSocketConfig)
        assert cfg.websocket.path == "/ws"

    def test_websocket_false_disables(self):
        cfg = HttpServerControllerAdapterConfig.model_validate({
            "type": "http-server", "websocket": False,
        })
        assert cfg.websocket is False

    def test_websocket_object_pass_through(self):
        cfg = HttpServerControllerAdapterConfig.model_validate({
            "type": "http-server",
            "websocket": {"path": "/custom", "ping_interval": "10s"},
        })
        assert cfg.websocket.path == "/custom"
        assert cfg.websocket.ping_interval == "10s"

    def test_default_websocket_when_omitted(self):
        cfg = HttpServerControllerAdapterConfig.model_validate({"type": "http-server"})
        assert isinstance(cfg.websocket, WebSocketConfig)
        assert cfg.websocket.path == "/ws"
