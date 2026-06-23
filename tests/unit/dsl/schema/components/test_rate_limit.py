"""Unit tests for ``mindor.dsl.schema.component.impl.rate_limit``.

Covers the pydantic validators on ``RateLimitConfig`` and the
``inflate_rate_limit_shorthand`` parser used to expand strings like ``"10/1s"``.
"""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.component.impl.rate_limit import (
    RateLimitConfig,
    inflate_rate_limit_shorthand,
)


class TestInflateShorthand:
    def test_requests_per_qualified_period(self):
        assert inflate_rate_limit_shorthand("10/1s") == {"requests": 10, "period": "1s"}

    def test_requests_per_fractional_period(self):
        assert inflate_rate_limit_shorthand("5/0.5s") == {"requests": 5, "period": "0.5s"}

    def test_requests_per_bare_unit(self):
        # `"10/s"` → "10 per second"; period normalised to "1s".
        assert inflate_rate_limit_shorthand("10/s") == {"requests": 10, "period": "1s"}

    def test_milliseconds_unit(self):
        assert inflate_rate_limit_shorthand("100/200ms") == {"requests": 100, "period": "200ms"}

    def test_with_whitespace(self):
        assert inflate_rate_limit_shorthand("  10 / 2m  ") == {"requests": 10, "period": "2m"}

    def test_invalid_shorthand_raises(self):
        with pytest.raises(ValueError, match="Invalid rate_limit shorthand"):
            inflate_rate_limit_shorthand("not-a-shorthand")

    def test_missing_unit_raises(self):
        with pytest.raises(ValueError, match="Invalid rate_limit shorthand"):
            inflate_rate_limit_shorthand("10/5")


class TestRateLimitConfigPositiveInts:
    def test_zero_requests_rejected(self):
        with pytest.raises(ValidationError, match="must be a positive integer"):
            RateLimitConfig(requests=0)

    def test_negative_burst_rejected(self):
        with pytest.raises(ValidationError, match="must be a positive integer"):
            RateLimitConfig(requests=5, burst=-1)

    def test_positive_values_accepted(self):
        cfg = RateLimitConfig(requests=10, burst=20)
        assert cfg.requests == 10
        assert cfg.burst == 20


class TestRateLimitConfigPositiveDurations:
    def test_zero_period_rejected(self):
        with pytest.raises(ValidationError, match="must be a positive duration"):
            RateLimitConfig(requests=1, period=0)

    def test_negative_period_rejected(self):
        with pytest.raises(ValidationError, match="must be a positive duration"):
            RateLimitConfig(requests=1, period=-1)

    def test_negative_interval_rejected(self):
        with pytest.raises(ValidationError, match="must be a positive duration"):
            RateLimitConfig(requests=1, interval=-0.5)

    def test_period_string_format(self):
        cfg = RateLimitConfig(requests=1, period="500ms")
        assert cfg.period == "500ms"


class TestRateLimitConfigGates:
    def test_burst_without_requests_rejected(self):
        with pytest.raises(ValidationError, match="burst is meaningless without requests"):
            RateLimitConfig(burst=5, interval="1s")

    def test_neither_requests_nor_interval_rejected(self):
        with pytest.raises(ValidationError, match="at least one of 'requests' or 'interval'"):
            RateLimitConfig()

    def test_only_interval_ok(self):
        cfg = RateLimitConfig(interval="100ms")
        assert cfg.interval == "100ms"

    def test_only_requests_ok(self):
        cfg = RateLimitConfig(requests=5)
        assert cfg.requests == 5

    def test_requests_without_period_defaults_to_1s(self):
        cfg = RateLimitConfig(requests=5)
        assert cfg.period == "1s"

    def test_period_without_requests_rejected(self):
        with pytest.raises(ValidationError, match="period is meaningless without requests"):
            RateLimitConfig(period="2s", interval="100ms")

    def test_full_combination_ok(self):
        cfg = RateLimitConfig(requests=10, period="1s", burst=20, interval="50ms")
        assert (cfg.requests, cfg.period, cfg.burst, cfg.interval) == (10, "1s", 20, "50ms")
