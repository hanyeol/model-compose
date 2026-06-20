"""Unit tests for ``ComponentJobConfig`` validators (interrupt point normalisation
and ``repeat_count`` validation)."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.job.impl.component import (
    ComponentInterruptConfig,
    ComponentInterruptPointConfig,
    ComponentJobConfig,
)


class TestInterruptPointNormalisation:
    def test_before_true_inflated_to_default_point(self):
        cfg = ComponentInterruptConfig(before=True)
        assert isinstance(cfg.before, ComponentInterruptPointConfig)

    def test_before_false_stays_false(self):
        cfg = ComponentInterruptConfig(before=False)
        assert cfg.before is False

    def test_before_none_treated_as_false(self):
        cfg = ComponentInterruptConfig(before=None)
        assert cfg.before is False

    def test_explicit_point_object_preserved(self):
        cfg = ComponentInterruptConfig(after={"message": "stop here"})
        assert isinstance(cfg.after, ComponentInterruptPointConfig)
        assert cfg.after.message == "stop here"

    def test_default_values_are_false(self):
        cfg = ComponentInterruptConfig()
        assert cfg.before is False and cfg.after is False


class TestRepeatCountValidation:
    def test_default_is_one(self):
        cfg = ComponentJobConfig(type="component")
        assert cfg.repeat_count == 1

    def test_positive_int_ok(self):
        cfg = ComponentJobConfig(type="component", repeat_count=5)
        assert cfg.repeat_count == 5

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="'repeat_count' must be at least 1"):
            ComponentJobConfig(type="component", repeat_count=0)

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="'repeat_count' must be at least 1"):
            ComponentJobConfig(type="component", repeat_count=-3)

    def test_template_string_accepted(self):
        # Templates are deferred to runtime; the int-bound check only fires for ints.
        cfg = ComponentJobConfig(type="component", repeat_count="${input.n}")
        assert cfg.repeat_count == "${input.n}"
