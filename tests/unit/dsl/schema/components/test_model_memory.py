"""Unit tests for ``ModelMemoryComponentConfig`` and ``ModelMemoryWindowConfig``."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.component.impl.model_memory.model_memory import (
    ModelMemoryComponentConfig,
    ModelMemoryWindowConfig,
)


class TestWindowConfigValidateLimits:
    def test_max_turn_count_only_ok(self):
        cfg = ModelMemoryWindowConfig(max_turn_count=5)
        assert cfg.max_turn_count == 5

    def test_max_message_count_only_ok(self):
        cfg = ModelMemoryWindowConfig(max_message_count=20)
        assert cfg.max_message_count == 20

    def test_both_limits_ok(self):
        cfg = ModelMemoryWindowConfig(max_turn_count=3, max_message_count=10)
        assert (cfg.max_turn_count, cfg.max_message_count) == (3, 10)

    def test_neither_limit_rejected(self):
        with pytest.raises(ValidationError, match="window requires at least one of max_turn_count or max_message_count"):
            ModelMemoryWindowConfig()


class TestInflateWindow:
    def test_int_window_inflated_to_max_turn_count(self):
        cfg = ModelMemoryComponentConfig(type="model-memory", window=5)
        assert cfg.window.max_turn_count == 5
        assert cfg.window.max_message_count is None

    def test_dict_window_passes_through(self):
        cfg = ModelMemoryComponentConfig(type="model-memory", window={"max_message_count": 20})
        assert cfg.window.max_turn_count is None
        assert cfg.window.max_message_count == 20

    def test_no_window_stays_none(self):
        cfg = ModelMemoryComponentConfig(type="model-memory")
        assert cfg.window is None
