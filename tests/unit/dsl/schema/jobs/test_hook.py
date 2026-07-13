"""Unit tests for JobHooksConfig normalisation on CommonJobConfig."""

import pytest

from mindor.dsl.schema.job.impl.common import (
    JobHookConfig,
    JobHooksConfig,
)
from mindor.dsl.schema.job.impl.component import ComponentJobConfig


SCRIPT = "async def hook(id, x):\n    return x\n"


class TestJobHooksNormalisation:
    def test_default_phases_are_empty_lists(self):
        cfg = JobHooksConfig()
        assert cfg.before == []
        assert cfg.after == []

    def test_single_dict_is_wrapped_to_list(self):
        cfg = JobHooksConfig(before={"script": SCRIPT})
        assert isinstance(cfg.before, list) and len(cfg.before) == 1
        assert isinstance(cfg.before[0], JobHookConfig)
        assert cfg.before[0].script == SCRIPT

    def test_list_of_dicts_stays_as_list(self):
        cfg = JobHooksConfig(after=[{"script": SCRIPT}, {"script": SCRIPT}])
        assert len(cfg.after) == 2
        assert all(isinstance(h, JobHookConfig) for h in cfg.after)

    def test_omitted_phase_defaults_to_empty(self):
        cfg = JobHooksConfig(before={"script": SCRIPT})
        assert cfg.after == []

    def test_empty_list_stays_empty(self):
        cfg = JobHooksConfig(before=[])
        assert cfg.before == []


class TestJobHookOnComponentJobConfig:
    def test_hook_field_available_on_component_job(self):
        cfg = ComponentJobConfig(
            type="component",
            hook={
                "before": {"script": SCRIPT},
                "after": [{"script": SCRIPT}, {"script": SCRIPT}],
            },
        )
        assert cfg.hook is not None
        assert len(cfg.hook.before) == 1
        assert len(cfg.hook.after) == 2

    def test_hook_default_is_none(self):
        cfg = ComponentJobConfig(type="component")
        assert cfg.hook is None
