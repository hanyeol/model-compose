"""Unit tests for ``HttpCallbackListenerConfig`` schema validation."""

from mindor.dsl.schema.listener.impl.http_callback import (
    HttpCallbackConfig,
    HttpCallbackListenerConfig,
)


class TestStatusFieldNormalisation:
    """``success_when`` and ``fail_when`` accept a single value as shorthand
    for a one-element list."""

    def test_single_string_wrapped(self):
        cfg = HttpCallbackConfig(path="/cb", success_when="ok")
        assert cfg.success_when == ["ok"]

    def test_explicit_list_pass_through(self):
        cfg = HttpCallbackConfig(path="/cb", fail_when=["error", "timeout"])
        assert cfg.fail_when == ["error", "timeout"]


class TestInlineCallbackShorthand:
    """Top-level path/method/etc. are a shorthand for a single-item
    ``callbacks`` list."""

    def test_inline_fields_inflated_into_single_callback(self):
        cfg = HttpCallbackListenerConfig.model_validate({
            "type": "http-callback",
            "path": "/cb",
            "method": "POST",
        })
        assert len(cfg.callbacks) == 1
        assert cfg.callbacks[0].path == "/cb"

    def test_explicit_callbacks_list_pass_through(self):
        cfg = HttpCallbackListenerConfig.model_validate({
            "type": "http-callback",
            "callbacks": [
                {"path": "/a"},
                {"path": "/b"},
            ],
        })
        assert len(cfg.callbacks) == 2
