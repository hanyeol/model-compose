"""Unit tests for ``IfJobConfig`` schema validation."""

from mindor.dsl.schema.job.impl.if_ import IfJobConfig


class TestInlineConditionShorthand:
    """Top-level operator/value/if_true/if_false are a shorthand for a
    single-item ``conditions`` list."""

    def test_inline_fields_inflated_into_single_condition(self):
        cfg = IfJobConfig.model_validate({
            "type": "if",
            "operator": "eq",
            "value": "approved",
            "if_true": "approved-job",
            "if_false": "rejected-job",
        })
        assert len(cfg.conditions) == 1
        assert cfg.conditions[0].operator.value == "eq"
        assert cfg.conditions[0].value == "approved"
        assert cfg.conditions[0].if_true == "approved-job"

    def test_explicit_conditions_list_pass_through(self):
        cfg = IfJobConfig.model_validate({
            "type": "if",
            "conditions": [
                {"operator": "eq", "value": "a", "if_true": "ja"},
                {"operator": "neq", "value": "b", "if_true": "jb"},
            ],
        })
        assert len(cfg.conditions) == 2

    def test_omitted_conditions_yields_empty_list(self):
        cfg = IfJobConfig.model_validate({"type": "if"})
        assert cfg.conditions == []


class TestRoutingTargets:
    def test_routing_jobs_include_branches_and_otherwise(self):
        cfg = IfJobConfig.model_validate({
            "type": "if",
            "conditions": [
                {"value": "a", "if_true": "ja", "if_false": "jb"},
            ],
            "otherwise": "default-job",
        })
        assert cfg.get_routing_jobs() == {"ja", "jb", "default-job"}
