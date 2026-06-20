"""Unit tests for the shared validators on ``CommonComponentConfig``.

Covers the cross-cutting validators that apply to every component config:
``validate_id``, ``inflate_single_action``, and ``inflate_runtime``.
Component-specific validators have their own test files.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import RuntimeType


ComponentAdapter = TypeAdapter(ComponentConfig)


def _minimal_shell(**overrides) -> dict:
    raw: dict = {
        "id": "c1",
        "type": "shell",
        "action": {"command": ["echo", "hi"]},
    }
    raw.update(overrides)
    return raw


class TestValidateId:
    def test_default_id_rejected(self):
        with pytest.raises(ValidationError, match="Component id cannot be '__default__'"):
            ComponentAdapter.validate_python(_minimal_shell(id="__default__"))

    def test_normal_id_accepted(self):
        config = ComponentAdapter.validate_python(_minimal_shell(id="custom-id"))
        assert config.id == "custom-id"

    def test_omitted_id_uses_placeholder(self):
        raw = _minimal_shell()
        del raw["id"]
        config = ComponentAdapter.validate_python(raw)
        assert config.id == "__component__"


class TestInflateSingleAction:
    def test_single_action_key_inflated_to_list(self):
        config = ComponentAdapter.validate_python(_minimal_shell())
        assert len(config.actions) == 1

    def test_explicit_actions_list_passes_through(self):
        raw = {
            "id": "c1",
            "type": "shell",
            "actions": [
                {"command": ["echo", "a"]},
                {"command": ["echo", "b"]},
            ],
        }
        config = ComponentAdapter.validate_python(raw)
        assert len(config.actions) == 2

    def test_actions_key_wins_over_action_when_both_present(self):
        # `inflate_single_action` only fills `actions` when missing — if `actions`
        # already exists, the `action` key is left alone.
        raw = {
            "id": "c1",
            "type": "shell",
            "action": {"command": ["echo", "single"]},
            "actions": [{"command": ["echo", "list"]}],
        }
        config = ComponentAdapter.validate_python(raw)
        assert len(config.actions) == 1
        assert config.actions[0].command == ["echo", "list"]


class TestInflateRuntime:
    def test_no_runtime_defaults_to_native(self):
        config = ComponentAdapter.validate_python(_minimal_shell())
        assert config.runtime.type == RuntimeType.NATIVE

    def test_runtime_string_shorthand_inflated_to_object(self):
        config = ComponentAdapter.validate_python(_minimal_shell(runtime="native"))
        assert config.runtime.type == RuntimeType.NATIVE

    def test_runtime_object_passes_through(self):
        config = ComponentAdapter.validate_python(_minimal_shell(runtime={"type": "native"}))
        assert config.runtime.type == RuntimeType.NATIVE
