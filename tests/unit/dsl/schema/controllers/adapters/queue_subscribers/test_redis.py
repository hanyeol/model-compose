"""Unit tests for ``RedisQueueSubscriberControllerAdapterConfig`` schema validation."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.controller.adapter.impl.queue_subscriber.impl.redis import (
    RedisQueueSubscriberControllerAdapterConfig,
)


class TestConnection:
    def test_url_only_ok(self):
        cfg = RedisQueueSubscriberControllerAdapterConfig(
            type="queue-subscriber", driver="redis", url="redis://q:6379",
        )
        assert cfg.url == "redis://q:6379"

    def test_url_and_host_together_rejected(self):
        with pytest.raises(ValidationError, match="Either 'url' or 'host'"):
            RedisQueueSubscriberControllerAdapterConfig(
                type="queue-subscriber", driver="redis", url="redis://x", host="other",
            )
