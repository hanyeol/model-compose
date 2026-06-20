"""Unit tests for ``mindor.core.utils.caching.ExpiringDict``."""

import time

from mindor.core.utils.caching import ExpiringDict


class TestSetAndGet:
    def test_set_then_get_returns_value(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.set("k", "v")
        assert d.get("k") == "v"

    def test_get_missing_returns_none(self):
        d: ExpiringDict[str] = ExpiringDict()
        assert d.get("missing") is None

    def test_set_without_expiry_persists(self):
        d: ExpiringDict[int] = ExpiringDict()
        d.set("k", 42)
        time.sleep(0.05)
        assert d.get("k") == 42

    def test_overwrite_replaces_value(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.set("k", "v1")
        d.set("k", "v2")
        assert d.get("k") == "v2"


class TestExpiry:
    def test_expired_get_returns_none_and_evicts(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.set("k", "v", expires_in=0.01)
        time.sleep(0.02)
        assert d.get("k") is None
        # Internal eviction on get — keys() should not see it either.
        assert "k" not in d.keys()

    def test_non_expired_get_returns_value(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.set("k", "v", expires_in=1.0)
        assert d.get("k") == "v"


class TestHas:
    def test_has_true_for_unexpired(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.set("k", "v")
        assert d.has("k") is True

    def test_has_false_for_expired(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.set("k", "v", expires_in=0.01)
        time.sleep(0.02)
        assert d.has("k") is False

    def test_has_false_for_missing(self):
        d: ExpiringDict[str] = ExpiringDict()
        assert d.has("nope") is False


class TestRemove:
    def test_remove_existing(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.set("k", "v")
        d.remove("k")
        assert d.get("k") is None

    def test_remove_missing_is_noop(self):
        d: ExpiringDict[str] = ExpiringDict()
        d.remove("nope")  # must not raise


class TestKeys:
    def test_returns_only_unexpired_keys(self):
        d: ExpiringDict[int] = ExpiringDict()
        d.set("forever", 1)
        d.set("transient", 2, expires_in=0.01)
        time.sleep(0.02)
        keys = d.keys()
        assert "forever" in keys
        assert "transient" not in keys


class TestCleanup:
    def test_cleanup_removes_only_expired(self):
        d: ExpiringDict[int] = ExpiringDict()
        d.set("a", 1)
        d.set("b", 2, expires_in=0.01)
        time.sleep(0.02)
        d.cleanup()
        assert d.get("a") == 1
        assert "b" not in d.keys()
