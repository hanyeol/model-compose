"""Unit tests for ``mindor.core.evaluator.condition.evaluate_condition``."""

import pytest

from mindor.core.evaluator.condition import evaluate_condition
from mindor.dsl.schema.operator.condition import ConditionOperator


class TestEquality:
    def test_eq_true(self):
        assert evaluate_condition(ConditionOperator.EQ, 5, 5) is True

    def test_eq_false(self):
        assert evaluate_condition(ConditionOperator.EQ, 5, 6) is False

    def test_eq_strings(self):
        assert evaluate_condition(ConditionOperator.EQ, "hello", "hello") is True

    def test_neq_true(self):
        assert evaluate_condition(ConditionOperator.NEQ, 5, 6) is True

    def test_neq_false(self):
        assert evaluate_condition(ConditionOperator.NEQ, "a", "a") is False


class TestOrdering:
    def test_gt(self):
        assert evaluate_condition(ConditionOperator.GT, 10, 5) is True
        assert evaluate_condition(ConditionOperator.GT, 5, 5) is False

    def test_gte(self):
        assert evaluate_condition(ConditionOperator.GTE, 5, 5) is True
        assert evaluate_condition(ConditionOperator.GTE, 5, 6) is False

    def test_lt(self):
        assert evaluate_condition(ConditionOperator.LT, 4, 5) is True
        assert evaluate_condition(ConditionOperator.LT, 5, 5) is False

    def test_lte(self):
        assert evaluate_condition(ConditionOperator.LTE, 5, 5) is True
        assert evaluate_condition(ConditionOperator.LTE, 6, 5) is False


class TestMembership:
    def test_in_list(self):
        assert evaluate_condition(ConditionOperator.IN, 2, [1, 2, 3]) is True
        assert evaluate_condition(ConditionOperator.IN, 4, [1, 2, 3]) is False

    def test_in_string_substring(self):
        assert evaluate_condition(ConditionOperator.IN, "lo", "hello") is True

    def test_not_in_list(self):
        assert evaluate_condition(ConditionOperator.NOT_IN, 4, [1, 2, 3]) is True
        assert evaluate_condition(ConditionOperator.NOT_IN, 2, [1, 2, 3]) is False


class TestMatch:
    def test_match_simple(self):
        assert evaluate_condition(ConditionOperator.MATCH, "hello", r"h.*o") is True

    def test_match_anchored_at_start(self):
        # re.match anchors at start but not at end
        assert evaluate_condition(ConditionOperator.MATCH, "hello world", "hello") is True
        assert evaluate_condition(ConditionOperator.MATCH, "world hello", "hello") is False

    def test_match_no_match(self):
        assert evaluate_condition(ConditionOperator.MATCH, "hello", r"\d+") is False


class TestUnsupportedOperator:
    def test_starts_with_not_implemented_raises(self):
        # STARTS_WITH / ENDS_WITH are declared in the enum but evaluate_condition
        # doesn't handle them — guarding the dispatch as the spec.
        with pytest.raises(ValueError, match="Unsupported operator"):
            evaluate_condition(ConditionOperator.STARTS_WITH, "hello", "he")

    def test_ends_with_not_implemented_raises(self):
        with pytest.raises(ValueError, match="Unsupported operator"):
            evaluate_condition(ConditionOperator.ENDS_WITH, "hello", "lo")
