"""Unit tests for ``ControllerConfig`` schema validation."""

from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.controller.webui import ControllerWebUIDriver
from mindor.dsl.schema.runtime import RuntimeType


class TestAdapterShorthand:
    """Top-level ``adapter`` is a shorthand for a single-item ``adapters`` list."""

    def test_single_adapter_inflated_to_list(self):
        cfg = ControllerConfig.model_validate({
            "adapter": {"type": "http-server", "port": 8080},
        })
        assert len(cfg.adapters) == 1
        assert cfg.adapters[0].port == 8080

    def test_explicit_adapters_list_pass_through(self):
        cfg = ControllerConfig.model_validate({
            "adapters": [
                {"type": "http-server", "port": 8080},
                {"type": "http-server", "port": 8081},
            ],
        })
        assert len(cfg.adapters) == 2


class TestRuntimeShorthand:
    """``runtime`` accepts a string (e.g. ``"native"``) as shorthand for
    ``{"type": "native"}``; omitting it defaults to native."""

    def test_omitted_runtime_defaults_to_native(self):
        cfg = ControllerConfig.model_validate({})
        assert cfg.runtime.type == RuntimeType.NATIVE

    def test_string_runtime_inflated_to_object(self):
        cfg = ControllerConfig.model_validate({"runtime": "native"})
        assert cfg.runtime.type == RuntimeType.NATIVE

    def test_explicit_runtime_object_pass_through(self):
        cfg = ControllerConfig.model_validate({"runtime": {"type": "native"}})
        assert cfg.runtime.type == RuntimeType.NATIVE


class TestWebUIDefault:
    """If ``webui`` is provided without a driver, the Gradio driver is assumed."""

    def test_webui_without_driver_defaults_to_gradio(self):
        cfg = ControllerConfig.model_validate({"webui": {"port": 7860}})
        assert cfg.webui.driver == ControllerWebUIDriver.GRADIO

    def test_explicit_driver_pass_through(self):
        cfg = ControllerConfig.model_validate({"webui": {"driver": "gradio", "port": 7860}})
        assert cfg.webui.driver == ControllerWebUIDriver.GRADIO

    def test_omitted_webui_stays_none(self):
        cfg = ControllerConfig.model_validate({})
        assert cfg.webui is None
