"""Unit tests for ``HttpServerPollingCompletionConfig`` validators."""

from mindor.dsl.schema.action.impl.http_server import HttpServerPollingCompletionConfig


class TestNormalizeStatusFields:
    def test_single_int_inflated_to_list(self):
        cfg = HttpServerPollingCompletionConfig(type="polling", success_when=200)
        assert cfg.success_when == [200]

    def test_single_string_inflated_to_list(self):
        cfg = HttpServerPollingCompletionConfig(type="polling", fail_when="error")
        assert cfg.fail_when == ["error"]

    def test_explicit_list_passes_through(self):
        cfg = HttpServerPollingCompletionConfig(
            type="polling", success_when=[200, 201], fail_when=["fail", "error"]
        )
        assert cfg.success_when == [200, 201]
        assert cfg.fail_when == ["fail", "error"]

    def test_omitted_status_fields_stay_none(self):
        cfg = HttpServerPollingCompletionConfig(type="polling")
        assert cfg.success_when is None
        assert cfg.fail_when is None
