"""Unit tests for ``HttpTriggerListenerConfig`` schema validation."""

from mindor.dsl.schema.listener.impl.http_trigger import HttpTriggerListenerConfig


class TestInlineTriggerShorthand:
    """Top-level path/workflow/etc. are a shorthand for a single-item
    ``triggers`` list."""

    def test_inline_fields_inflated_into_single_trigger(self):
        cfg = HttpTriggerListenerConfig.model_validate({
            "type": "http-trigger",
            "path": "/run",
            "workflow": "wf",
        })
        assert len(cfg.triggers) == 1
        assert cfg.triggers[0].path == "/run"
        assert cfg.triggers[0].workflow == "wf"

    def test_explicit_triggers_list_pass_through(self):
        cfg = HttpTriggerListenerConfig.model_validate({
            "type": "http-trigger",
            "triggers": [
                {"path": "/run-a", "workflow": "wfa"},
                {"path": "/run-b", "workflow": "wfb"},
            ],
        })
        assert len(cfg.triggers) == 2
