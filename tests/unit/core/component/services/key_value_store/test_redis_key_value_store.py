"""Tests for the Redis key-value store component, action schema, and service layer."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from unittest.mock import AsyncMock, MagicMock, call

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
    """Mock ComponentActionContext with real ArrayValue rendering.

    The Redis driver goes through ``render_array`` for keys/values and
    ``render_variable`` for other config fields, so those need working
    implementations. Everything else stays mocked so tests can assert on it.
    """
    from mindor.core.foundation.variable.array import ArrayValueRenderer

    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None

    async def render_variable(value, **kwargs):
        return value
    context.render_variable = AsyncMock(side_effect=render_variable)

    async def render_array(value, single_as_array=False):
        return await ArrayValueRenderer().render(value, single_as_array)
    context.render_array = AsyncMock(side_effect=render_array)

    context.register_source = MagicMock()
    return context


def _make_pipeline():
    """Build an async-context-manager pipeline mock that records commands."""
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=None)
    # Command builders (setex/delete/exists) are sync on the pipeline object.
    pipe.setex = MagicMock()
    pipe.delete = MagicMock()
    pipe.exists = MagicMock()
    return pipe


class TestRedisKeyValueStoreActionUnit:
    """Unit tests with mocked Redis client — single-key inputs.

    Result shape for a single key is a single dict (not a list):
      - GET    str → ``{"key": k, "value": <decoded>}``      (MGET [k])
      - SET    str → ``{"key": k, "success": True}``         (MSET or pipelined SETEX)
      - DELETE str → ``{"key": k, "deleted": bool}``         (pipelined DEL k)
      - EXISTS str → ``{"key": k, "exists": bool}``          (pipelined EXISTS k)
    The driver always batches — even a single key goes through MGET / MSET / pipelines.
    """

    @pytest.mark.anyio
    async def test_get_existing_key(self, mock_context):
        """Verify GET returns the deserialized value for an existing key."""
        client = AsyncMock()
        client.mget = AsyncMock(return_value=[b'"hello"'])

        config = RedisKeyValueGetActionConfig(method="get", key="test-key")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.mget.assert_called_once_with(["test-key"])
        assert result == {"key": "test-key", "value": "hello"}
        mock_context.register_source.assert_called_once_with("result", {"key": "test-key", "value": "hello"})

    @pytest.mark.anyio
    async def test_get_missing_key(self, mock_context):
        """Verify GET returns None for a missing key."""
        client = AsyncMock()
        client.mget = AsyncMock(return_value=[None])

        config = RedisKeyValueGetActionConfig(method="get", key="missing")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert result == {"key": "missing", "value": None}

    @pytest.mark.anyio
    async def test_get_json_object(self, mock_context):
        """Verify GET deserializes a JSON object value."""
        client = AsyncMock()
        client.mget = AsyncMock(return_value=[b'{"name": "Alice", "age": 30}'])

        config = RedisKeyValueGetActionConfig(method="get", key="user:1")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert result["value"] == {"name": "Alice", "age": 30}

    @pytest.mark.anyio
    async def test_get_plain_string(self, mock_context):
        """Verify GET returns a plain string when the value is not valid JSON."""
        client = AsyncMock()
        client.mget = AsyncMock(return_value=[b"plain text"])

        config = RedisKeyValueGetActionConfig(method="get", key="msg")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert result["value"] == "plain text"

    @pytest.mark.anyio
    async def test_set_string_no_ttl(self, mock_context):
        """Verify SET without TTL uses MSET."""
        client = AsyncMock()
        client.mset = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="k", value="v")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.mset.assert_called_once_with({"k": "v"})
        assert result == {"key": "k", "success": True}

    @pytest.mark.anyio
    async def test_set_with_ttl(self, mock_context):
        """Verify SET with TTL uses a pipelined SETEX."""
        pipe = _make_pipeline()
        pipe.execute = AsyncMock(return_value=[True])
        client = AsyncMock()
        client.pipeline = MagicMock(return_value=pipe)

        config = RedisKeyValueSetActionConfig(method="set", key="k", value="v", ttl=60)
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.pipeline.assert_called_once_with(transaction=False)
        pipe.setex.assert_called_once_with("k", 60, "v")
        assert result == {"key": "k", "success": True}

    @pytest.mark.anyio
    async def test_set_dict_value_serialized(self, mock_context):
        """Verify SET serializes dict values as JSON."""
        client = AsyncMock()
        client.mset = AsyncMock(return_value=True)

        data = {"name": "Alice", "roles": ["admin"]}
        config = RedisKeyValueSetActionConfig(method="set", key="user", value=data)
        await RedisKeyValueStoreAction(config, client).run(mock_context)

        stored = client.mset.call_args[0][0]
        assert set(stored.keys()) == {"user"}
        assert json.loads(stored["user"]) == data

    @pytest.mark.anyio
    async def test_set_list_value_serialized(self, mock_context):
        """Verify SET serializes list values as JSON.

        A single-key SET stores the list intact rather than splitting entries
        across per-key writes.
        """
        client = AsyncMock()
        client.mset = AsyncMock(return_value=True)

        data = [1, 2, 3]
        config = RedisKeyValueSetActionConfig(method="set", key="nums", value=data)
        await RedisKeyValueStoreAction(config, client).run(mock_context)

        stored = client.mset.call_args[0][0]
        assert json.loads(stored["nums"]) == [1, 2, 3]

    @pytest.mark.anyio
    async def test_set_int_value_to_string(self, mock_context):
        """Verify SET converts non-string, non-JSON values to string."""
        client = AsyncMock()
        client.mset = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="count", value=42)
        await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert client.mset.call_args[0][0]["count"] == "42"

    @pytest.mark.anyio
    async def test_delete(self, mock_context):
        """Verify DELETE uses a pipelined DEL and reports per-key removal."""
        pipe = _make_pipeline()
        pipe.execute = AsyncMock(return_value=[1])
        client = AsyncMock()
        client.pipeline = MagicMock(return_value=pipe)

        config = RedisKeyValueDeleteActionConfig(method="delete", key="k")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        pipe.delete.assert_called_once_with("k")
        assert result == {"key": "k", "deleted": True}

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, mock_context):
        """Verify DELETE on a nonexistent key reports ``deleted=False``."""
        pipe = _make_pipeline()
        pipe.execute = AsyncMock(return_value=[0])
        client = AsyncMock()
        client.pipeline = MagicMock(return_value=pipe)

        config = RedisKeyValueDeleteActionConfig(method="delete", key="missing")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert result == {"key": "missing", "deleted": False}

    @pytest.mark.anyio
    async def test_exists_true(self, mock_context):
        """Verify EXISTS returns True for an existing key."""
        pipe = _make_pipeline()
        pipe.execute = AsyncMock(return_value=[1])
        client = AsyncMock()
        client.pipeline = MagicMock(return_value=pipe)

        config = RedisKeyValueExistsActionConfig(method="exists", key="k")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        pipe.exists.assert_called_once_with("k")
        assert result == {"key": "k", "exists": True}

    @pytest.mark.anyio
    async def test_exists_false(self, mock_context):
        """Verify EXISTS returns False for a nonexistent key."""
        pipe = _make_pipeline()
        pipe.execute = AsyncMock(return_value=[0])
        client = AsyncMock()
        client.pipeline = MagicMock(return_value=pipe)

        config = RedisKeyValueExistsActionConfig(method="exists", key="missing")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert result == {"key": "missing", "exists": False}


class TestRedisKeyValueStoreIOMatrix:
    """I/O matrix for GET / SET / DELETE / EXISTS with list-key inputs.

    Result shape for list-key inputs is a list of per-key dicts:
      - GET    list → ``[{"key": k, "value": v}, ...]``      (single MGET)
      - SET    list → ``[{"key": k, "success": bool}, ...]`` (single MSET, or pipelined SETEX with TTL)
      - DELETE list → ``[{"key": k, "deleted": bool}, ...]`` (pipelined DEL per key)
      - EXISTS list → ``[{"key": k, "exists":  bool}, ...]`` (pipelined EXISTS per key)
    The driver batches natively (MGET / MSET / pipelines) so one request maps
    to one round-trip regardless of list length.
    """

    @pytest.mark.anyio
    async def test_get_list_keys_uses_mget(self, mock_context):
        client = AsyncMock()
        client.mget = AsyncMock(return_value=[b'"a"', b'"b"', None])

        config = RedisKeyValueGetActionConfig(method="get", key=["k1", "k2", "k3"])
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.mget.assert_called_once_with(["k1", "k2", "k3"])
        assert result == [
            {"key": "k1", "value": "a"},
            {"key": "k2", "value": "b"},
            {"key": "k3", "value": None},
        ]

    @pytest.mark.anyio
    async def test_set_list_keys_uses_mset(self, mock_context):
        client = AsyncMock()
        client.mset = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key=["k1", "k2"], value=["v1", "v2"])
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.mset.assert_called_once_with({"k1": "v1", "k2": "v2"})
        assert result == [
            {"key": "k1", "success": True},
            {"key": "k2", "success": True},
        ]

    @pytest.mark.anyio
    async def test_set_list_keys_broadcasts_single_value(self, mock_context):
        """A single value paired with a list of keys is broadcast to every key."""
        client = AsyncMock()
        client.mset = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key=["k1", "k2"], value="shared")
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        client.mset.assert_called_once_with({"k1": "shared", "k2": "shared"})
        assert len(result) == 2

    @pytest.mark.anyio
    async def test_delete_list_keys_uses_pipeline(self, mock_context):
        pipe = _make_pipeline()
        pipe.execute = AsyncMock(return_value=[1, 0, 1])
        client = AsyncMock()
        client.pipeline = MagicMock(return_value=pipe)

        config = RedisKeyValueDeleteActionConfig(method="delete", key=["k1", "k2", "k3"])
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert pipe.delete.call_args_list == [call("k1"), call("k2"), call("k3")]
        assert result == [
            {"key": "k1", "deleted": True},
            {"key": "k2", "deleted": False},
            {"key": "k3", "deleted": True},
        ]

    @pytest.mark.anyio
    async def test_exists_list_keys_uses_pipeline(self, mock_context):
        pipe = _make_pipeline()
        pipe.execute = AsyncMock(return_value=[1, 0])
        client = AsyncMock()
        client.pipeline = MagicMock(return_value=pipe)

        config = RedisKeyValueExistsActionConfig(method="exists", key=["k1", "k2"])
        result = await RedisKeyValueStoreAction(config, client).run(mock_context)

        assert pipe.exists.call_args_list == [call("k1"), call("k2")]
        assert result == [
            {"key": "k1", "exists": True},
            {"key": "k2", "exists": False},
        ]
