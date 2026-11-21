"""Unit tests for ``RuntimeRestartConfig``.

Lives on ``CommonRuntimeConfig`` so every concrete runtime inherits the
``restart:`` field. The scalar/dict shorthand mirrors docker-compose's
``restart`` key.
"""

import pytest

from mindor.dsl.schema.runtime.impl.common import (
    CommonRuntimeConfig,
    RuntimeRestartBackoff,
    RuntimeRestartConfig,
    RuntimeRestartPolicy,
)
from mindor.dsl.schema.runtime.impl.types import RuntimeType


class TestRuntimeRestartConfig:
    def test_defaults(self):
        cfg = RuntimeRestartConfig()
        assert cfg.policy == RuntimeRestartPolicy.NO
        assert cfg.max_attempt_count == 5
        assert cfg.window == "10m"
        assert cfg.delay == "2s"
        assert cfg.backoff == RuntimeRestartBackoff.EXPONENTIAL
        assert cfg.max_delay == "60s"

    def test_rejects_negative_max_attempt_count(self):
        with pytest.raises(ValueError):
            RuntimeRestartConfig(max_attempt_count=-1)

    def test_accepts_zero_max_attempt_count_as_unlimited(self):
        cfg = RuntimeRestartConfig(max_attempt_count=0)
        assert cfg.max_attempt_count == 0


class TestCommonRuntimeConfigRestartField:
    def test_restart_defaults_when_omitted(self):
        cfg = CommonRuntimeConfig(type=RuntimeType.PROCESS)
        assert isinstance(cfg.restart, RuntimeRestartConfig)
        assert cfg.restart.policy == RuntimeRestartPolicy.NO

    def test_scalar_shorthand_sets_policy(self):
        cfg = CommonRuntimeConfig(type=RuntimeType.PROCESS, restart="on-failure")
        assert cfg.restart.policy == RuntimeRestartPolicy.ON_FAILURE
        assert cfg.restart.max_attempt_count == 5

    def test_scalar_always(self):
        cfg = CommonRuntimeConfig(type=RuntimeType.PROCESS, restart="always")
        assert cfg.restart.policy == RuntimeRestartPolicy.ALWAYS

    def test_dict_form_overrides_fields(self):
        cfg = CommonRuntimeConfig(
            type=RuntimeType.PROCESS,
            restart={
                "policy": "on-failure",
                "max_attempt_count": 3,
                "window": "5m",
                "delay": "100ms",
                "backoff": "fixed",
                "max_delay": "10s",
            },
        )
        assert cfg.restart.policy == RuntimeRestartPolicy.ON_FAILURE
        assert cfg.restart.max_attempt_count == 3
        assert cfg.restart.window == "5m"
        assert cfg.restart.delay == "100ms"
        assert cfg.restart.backoff == RuntimeRestartBackoff.FIXED
        assert cfg.restart.max_delay == "10s"
