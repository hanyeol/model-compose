"""Tests for the Redis key-value store component, action schema, and service layer."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from unittest.mock import AsyncMock, MagicMock

from mindor.dsl.schema.component import ComponentConfig, KeyValueStoreComponentConfig, KeyValueStoreDriver
from mindor.dsl.schema.action import (
    KeyValueStoreActionConfig,
    RedisKeyValueStoreActionConfig,
    KeyValueStoreActionMethod,
    RedisKeyValueGetActionConfig,
    RedisKeyValueSetActionConfig,
    RedisKeyValueDeleteActionConfig,
    RedisKeyValueExistsActionConfig,
)
from mindor.core.component.services.key_value_store.drivers.redis import (
    RedisKeyValueStoreAction,
    RedisKeyValueStoreService,
)
from mindor.core.component.context import ComponentActionContext


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


# ──────────────────────────────────────────────
# Schema Tests
# ──────────────────────────────────────────────


class TestKeyValueStoreSchema:
    """Test key-value-store component and action schema validation."""

    component_adapter = TypeAdapter(ComponentConfig)

    def test_minimal_redis_config(self):
        """Validate a minimal Redis component config with defaults."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "actions": [],
        })
        assert config.type.value == "key-value-store"
        assert config.driver == KeyValueStoreDriver.REDIS
        assert config.host == "localhost"
        assert config.port == 6379

    def test_redis_config_with_url(self):
        """Validate that a URL-based Redis config is accepted."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "url": "redis://myhost:6380/2",
            "actions": [],
        })
        assert config.url == "redis://myhost:6380/2"

    def test_redis_url_and_host_conflict(self):
        """Validate that specifying both url and host raises a validation error."""
        with pytest.raises(ValidationError, match="url.*host|host.*url"):
            self.component_adapter.validate_python({
                "id": "kv",
                "type": "key-value-store",
                "driver": "redis",
                "url": "redis://localhost:6379",
                "host": "other-host",
                "actions": [],
            })

    def test_redis_config_full(self):
        """Validate a fully-specified Redis config with all fields."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "host": "redis.internal",
            "port": 6380,
            "secure": True,
            "database": 3,
            "password": "secret",
            "actions": [],
        })
        assert config.host == "redis.internal"
        assert config.port == 6380
        assert config.secure is True
        assert config.database == 3
        assert config.password == "secret"

    def test_action_set(self):
        """Validate a SET action config with key, value, and ttl."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "actions": [
                {"id": "save", "method": "set", "key": "k", "value": "v", "ttl": 60},
            ],
        })
        action = config.actions[0]
        assert action.method == KeyValueStoreActionMethod.SET
        assert action.key == "k"
        assert action.value == "v"
        assert action.ttl == 60

    def test_action_get(self):
        """Validate a GET action config."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "actions": [
                {"id": "load", "method": "get", "key": "k"},
            ],
        })
        action = config.actions[0]
        assert action.method == KeyValueStoreActionMethod.GET
        assert action.key == "k"

    def test_action_delete(self):
        """Validate a DELETE action config."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "actions": [
                {"id": "rm", "method": "delete", "key": "k"},
            ],
        })
        assert config.actions[0].method == KeyValueStoreActionMethod.DELETE

    def test_action_exists(self):
        """Validate an EXISTS action config."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "actions": [
                {"id": "chk", "method": "exists", "key": "k"},
            ],
        })
        assert config.actions[0].method == KeyValueStoreActionMethod.EXISTS

    def test_multiple_actions(self):
        """Validate that multiple actions of different methods can coexist."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "actions": [
                {"id": "save", "method": "set", "key": "k", "value": "v"},
                {"id": "load", "method": "get", "key": "k"},
                {"id": "rm", "method": "delete", "key": "k"},
                {"id": "chk", "method": "exists", "key": "k"},
            ],
        })
        assert len(config.actions) == 4
        methods = [a.method for a in config.actions]
        assert methods == [
            KeyValueStoreActionMethod.SET,
            KeyValueStoreActionMethod.GET,
            KeyValueStoreActionMethod.DELETE,
            KeyValueStoreActionMethod.EXISTS,
        ]

    def test_set_action_ttl_none_by_default(self):
        """Validate that SET action ttl defaults to None."""
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "actions": [
                {"id": "save", "method": "set", "key": "k", "value": "v"},
            ],
        })
        assert config.actions[0].ttl is None

    def test_invalid_method(self):
        """Validate that an invalid action method raises a validation error."""
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "kv",
                "type": "key-value-store",
                "driver": "redis",
                "actions": [
                    {"id": "bad", "method": "invalid", "key": "k"},
                ],
            })


# ──────────────────────────────────────────────
# Unit Tests (mocked Redis)
# ──────────────────────────────────────────────


@pytest.fixture
def mock_context():
    """Create a mock ComponentActionContext with a passthrough render_variable."""
    context = MagicMock(spec=ComponentActionContext)
    async def render_variable(value, ignore_files=False):
        return value
    context.render_variable = AsyncMock(side_effect=render_variable)
    context.register_source = MagicMock()
    context.contains_variable_reference = MagicMock(return_value=False)
    return context


class TestRedisKeyValueStoreActionUnit:
    """Unit tests with mocked Redis client."""

    @pytest.mark.anyio
    async def test_get_existing_key(self, mock_context):
        """Verify GET returns the deserialized value for an existing key."""
        client = AsyncMock()
        client.get = AsyncMock(return_value=b'"hello"')

        config = RedisKeyValueGetActionConfig(method="get", key="test-key")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        client.get.assert_called_once_with("test-key")
        mock_context.register_source.assert_called_once_with("result", {"value": "hello"})

    @pytest.mark.anyio
    async def test_get_missing_key(self, mock_context):
        """Verify GET returns None for a missing key."""
        client = AsyncMock()
        client.get = AsyncMock(return_value=None)

        config = RedisKeyValueGetActionConfig(method="get", key="missing")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        mock_context.register_source.assert_called_once_with("result", {"value": None})

    @pytest.mark.anyio
    async def test_get_json_object(self, mock_context):
        """Verify GET deserializes a JSON object value."""
        client = AsyncMock()
        client.get = AsyncMock(return_value=b'{"name": "Alice", "age": 30}')

        config = RedisKeyValueGetActionConfig(method="get", key="user:1")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["value"] == {"name": "Alice", "age": 30}

    @pytest.mark.anyio
    async def test_get_plain_string(self, mock_context):
        """Verify GET returns a plain string when the value is not valid JSON."""
        client = AsyncMock()
        client.get = AsyncMock(return_value=b"plain text")

        config = RedisKeyValueGetActionConfig(method="get", key="msg")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["value"] == "plain text"

    @pytest.mark.anyio
    async def test_set_string_no_ttl(self, mock_context):
        """Verify SET stores a string value without TTL."""
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="k", value="v")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        client.set.assert_called_once_with("k", "v")
        registered = mock_context.register_source.call_args[0][1]
        assert registered["success"] is True

    @pytest.mark.anyio
    async def test_set_with_ttl(self, mock_context):
        """Verify SET with TTL uses SETEX."""
        client = AsyncMock()
        client.setex = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="k", value="v", ttl=60)
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        client.setex.assert_called_once_with("k", 60, "v")

    @pytest.mark.anyio
    async def test_set_dict_value_serialized(self, mock_context):
        """Verify SET serializes dict values as JSON."""
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        data = {"name": "Alice", "roles": ["admin"]}
        config = RedisKeyValueSetActionConfig(method="set", key="user", value=data)
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        call_args = client.set.call_args[0]
        assert call_args[0] == "user"
        assert json.loads(call_args[1]) == data

    @pytest.mark.anyio
    async def test_set_list_value_serialized(self, mock_context):
        """Verify SET serializes list values as JSON."""
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        data = [1, 2, 3]
        config = RedisKeyValueSetActionConfig(method="set", key="nums", value=data)
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        call_args = client.set.call_args[0]
        assert json.loads(call_args[1]) == [1, 2, 3]

    @pytest.mark.anyio
    async def test_set_int_value_to_string(self, mock_context):
        """Verify SET converts integer values to string."""
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="count", value=42)
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        call_args = client.set.call_args[0]
        assert call_args[1] == "42"

    @pytest.mark.anyio
    async def test_delete(self, mock_context):
        """Verify DELETE removes a key and reports the count."""
        client = AsyncMock()
        client.delete = AsyncMock(return_value=1)

        config = RedisKeyValueDeleteActionConfig(method="delete", key="k")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        client.delete.assert_called_once_with("k")
        registered = mock_context.register_source.call_args[0][1]
        assert registered["count"] == 1

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, mock_context):
        """Verify DELETE on a nonexistent key reports count of 0."""
        client = AsyncMock()
        client.delete = AsyncMock(return_value=0)

        config = RedisKeyValueDeleteActionConfig(method="delete", key="missing")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["count"] == 0

    @pytest.mark.anyio
    async def test_exists_true(self, mock_context):
        """Verify EXISTS returns True for an existing key."""
        client = AsyncMock()
        client.exists = AsyncMock(return_value=1)

        config = RedisKeyValueExistsActionConfig(method="exists", key="k")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["exists"] is True

    @pytest.mark.anyio
    async def test_exists_false(self, mock_context):
        """Verify EXISTS returns False for a nonexistent key."""
        client = AsyncMock()
        client.exists = AsyncMock(return_value=0)

        config = RedisKeyValueExistsActionConfig(method="exists", key="missing")
        action = RedisKeyValueStoreAction(config, client)
        result = await action.run(mock_context)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["exists"] is False


class TestRedisKeyValueStoreIOMatrix:
    """I/O matrix for GET / DELETE / EXISTS with single-key vs list-key inputs.

    The Redis driver uses batched commands (MGET / DELETE k1 k2 ... / EXISTS k1 k2 ...)
    for list-key inputs, producing a single aggregate dict rather than per-key entries:
      - GET    list  → ``{"values": [v1, v2, ...]}``        (MGET)
      - GET    str   → ``{"value":  v}``                    (GET)
      - DELETE list  → ``{"count":  n}``                    (DELETE k1 k2 ...)
      - DELETE str   → ``{"count":  n}``                    (DELETE k)
      - EXISTS list  → ``{"count":  n}``                    (EXISTS k1 k2 ...)
      - EXISTS str   → ``{"exists": bool}``                 (EXISTS k)
    The KV schema does not expose ``batch_size`` or ``${result[]}`` streaming —
    list-key splitting + per-key streaming would be a separate feature.
    """

    @pytest.mark.anyio
    async def test_get_list_keys_uses_mget(self, mock_context):
        client = AsyncMock()
        client.mget = AsyncMock(return_value=[b'"a"', b'"b"', None])

        config = RedisKeyValueGetActionConfig(method="get", key=["k1", "k2", "k3"])
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.mget.assert_called_once_with(["k1", "k2", "k3"])
        assert result == {"values": ["a", "b", None]}

    @pytest.mark.anyio
    async def test_get_single_key_returns_single_dict(self, mock_context):
        client = AsyncMock()
        client.get = AsyncMock(return_value=b'"hello"')

        config = RedisKeyValueGetActionConfig(method="get", key="solo")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.get.assert_called_once_with("solo")
        assert result == {"value": "hello"}

    @pytest.mark.anyio
    async def test_delete_list_keys_uses_batched_delete(self, mock_context):
        client = AsyncMock()
        client.delete = AsyncMock(return_value=2)

        config = RedisKeyValueDeleteActionConfig(method="delete", key=["k1", "k2", "k3"])
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.delete.assert_called_once_with("k1", "k2", "k3")
        assert result == {"count": 2}

    @pytest.mark.anyio
    async def test_exists_list_keys_uses_batched_exists(self, mock_context):
        client = AsyncMock()
        client.exists = AsyncMock(return_value=1)

        config = RedisKeyValueExistsActionConfig(method="exists", key=["k1", "k2"])
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.exists.assert_called_once_with("k1", "k2")
        assert result == {"count": 1}
