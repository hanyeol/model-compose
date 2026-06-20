"""Unit tests for ``SwitchJobConfig`` schema validation."""

from mindor.dsl.schema.job.impl.switch import SwitchJobConfig


class TestInlineCaseShorthand:
    """Top-level value/then are a shorthand for a single-item ``cases`` list."""

    def test_inline_fields_inflated_into_single_case(self):
        cfg = SwitchJobConfig.model_validate({
            "type": "switch",
            "value": "a",
            "then": "branch-a",
        })
        assert len(cfg.cases) == 1
        assert cfg.cases[0].value == "a"
        assert cfg.cases[0].then == "branch-a"

    def test_explicit_cases_list_pass_through(self):
        cfg = SwitchJobConfig.model_validate({
            "type": "switch",
            "cases": [
                {"value": "a", "then": "ja"},
                {"value": "b", "then": "jb"},
            ],
        })
        assert len(cfg.cases) == 2


class TestRoutingTargets:
    def test_routing_jobs_include_cases_and_otherwise(self):
        cfg = SwitchJobConfig.model_validate({
            "type": "switch",
            "cases": [
                {"value": "a", "then": "ja"},
                {"value": "b", "then": "jb"},
            ],
            "otherwise": "default-job",
        })
        assert cfg.get_routing_jobs() == {"ja", "jb", "default-job"}
