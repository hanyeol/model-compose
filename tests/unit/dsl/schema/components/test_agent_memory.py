"""Unit tests for ``AgentMemoryComponentConfig`` and ``AgentMemoryWindowConfig``."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.component.impl.agent_memory.agent_memory import (
    AgentMemoryComponentConfig,
    AgentMemoryWindowConfig,
)


class TestWindowConfigValidateLimits:
    def test_max_turn_count_only_ok(self):
        cfg = AgentMemoryWindowConfig(max_turn_count=5)
        assert cfg.max_turn_count == 5

    def test_max_message_count_only_ok(self):
        cfg = AgentMemoryWindowConfig(max_message_count=20)
        assert cfg.max_message_count == 20

    def test_both_limits_ok(self):
        cfg = AgentMemoryWindowConfig(max_turn_count=3, max_message_count=10)
        assert (cfg.max_turn_count, cfg.max_message_count) == (3, 10)

    def test_neither_limit_rejected(self):
        with pytest.raises(ValidationError, match="window requires at least one of max_turn_count or max_message_count"):
            AgentMemoryWindowConfig()


class TestInflateWindow:
    def test_int_window_inflated_to_max_turn_count(self):
        cfg = AgentMemoryComponentConfig(type="agent-memory", window=5)
        assert cfg.window.max_turn_count == 5
        assert cfg.window.max_message_count is None

    def test_dict_window_passes_through(self):
        cfg = AgentMemoryComponentConfig(type="agent-memory", window={"max_message_count": 20})
        assert cfg.window.max_turn_count is None
        assert cfg.window.max_message_count == 20

    def test_no_window_stays_none(self):
        cfg = AgentMemoryComponentConfig(type="agent-memory")
        assert cfg.window is None
