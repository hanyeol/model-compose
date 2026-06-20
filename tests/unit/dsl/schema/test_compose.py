"""Unit tests for the singular-to-list inflator validators on ``ComposeConfig``."""

from mindor.dsl.schema.compose import ComposeConfig


def _base() -> dict:
    return {"controller": {"adapter": {"type": "http-server", "port": 8080}}}


class TestSingularInflators:
    def test_single_component_inflated_to_list(self):
        cfg = ComposeConfig.model_validate({
            **_base(),
            "component": {
                "id": "c1",
                "type": "shell",
                "action": {"command": ["echo"]},
            },
        })
        assert len(cfg.components) == 1
        assert cfg.components[0].id == "c1"

    def test_single_workflow_inflated_to_list(self):
        cfg = ComposeConfig.model_validate({
            **_base(),
            "workflow": {"id": "wf", "jobs": []},
        })
        assert len(cfg.workflows) == 1
        assert cfg.workflows[0].id == "wf"

    def test_single_listener_inflated_to_list(self):
        cfg = ComposeConfig.model_validate({
            **_base(),
            "listener": {"type": "http-callback", "path": "/cb"},
        })
        assert len(cfg.listeners) == 1

    def test_single_gateway_inflated_to_list(self):
        cfg = ComposeConfig.model_validate({
            **_base(),
            "gateway": {"type": "http-tunnel", "driver": "ngrok"},
        })
        assert len(cfg.gateways) == 1

    def test_single_system_inflated_to_list(self):
        cfg = ComposeConfig.model_validate({
            **_base(),
            "system": {"type": "docker-compose"},
        })
        assert len(cfg.systems) == 1

    def test_explicit_plural_key_takes_precedence(self):
        # Per the inflator: it only fills `<plural>` when missing.
        cfg = ComposeConfig.model_validate({
            **_base(),
            "component": {"id": "from-singular", "type": "shell", "action": {"command": ["echo"]}},
            "components": [
                {"id": "from-plural", "type": "shell", "action": {"command": ["echo"]}},
            ],
        })
        assert len(cfg.components) == 1
        assert cfg.components[0].id == "from-plural"

    def test_empty_lists_when_neither_key_provided(self):
        cfg = ComposeConfig.model_validate(_base())
        assert cfg.components == []
        assert cfg.workflows == []
        assert cfg.listeners == []
