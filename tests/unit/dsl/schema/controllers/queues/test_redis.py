"""Unit tests for ``RedisControllerQueueConfig`` schema validation."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.controller.queue.impl.redis import RedisControllerQueueConfig


class TestConnection:
    def test_url_only_ok(self):
        cfg = RedisControllerQueueConfig(driver="redis", url="redis://q:6379/0")
        assert cfg.url == "redis://q:6379/0"

    def test_url_and_host_together_rejected(self):
        with pytest.raises(ValidationError, match="Either 'url' or 'host'"):
            RedisControllerQueueConfig(driver="redis", url="redis://x", host="other")
