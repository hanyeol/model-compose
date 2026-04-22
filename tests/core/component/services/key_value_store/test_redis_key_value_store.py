import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from pydantic import TypeAdapter, ValidationError

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
    return "asyncio"


# ──────────────────────────────────────────────
# Schema Tests
# ──────────────────────────────────────────────

class TestKeyValueStoreSchema:
    """Test key-value-store component and action schema validation."""

    component_adapter = TypeAdapter(ComponentConfig)

    def test_minimal_redis_config(self):
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
        config = self.component_adapter.validate_python({
            "id": "kv",
            "type": "key-value-store",
            "driver": "redis",
            "url": "redis://myhost:6380/2",
            "actions": [],
        })
        assert config.url == "redis://myhost:6380/2"

    def test_redis_url_and_host_conflict(self):
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
    context = MagicMock(spec=ComponentActionContext)
    async def render_variable(value, ignore_files=False):
        return value
    context.render_variable = AsyncMock(side_effect=render_variable)
    context.register_source = MagicMock()
    return context


class TestRedisKeyValueStoreActionUnit:
    """Unit tests with mocked Redis client."""

    @pytest.mark.anyio
    async def test_get_existing_key(self, mock_context):
        client = AsyncMock()
        client.get = AsyncMock(return_value=b'"hello"')

        config = RedisKeyValueGetActionConfig(method="get", key="test-key")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        client.get.assert_called_once_with("test-key")
        mock_context.register_source.assert_called_once_with("result", {"value": "hello"})

    @pytest.mark.anyio
    async def test_get_missing_key(self, mock_context):
        client = AsyncMock()
        client.get = AsyncMock(return_value=None)

        config = RedisKeyValueGetActionConfig(method="get", key="missing")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        mock_context.register_source.assert_called_once_with("result", {"value": None})

    @pytest.mark.anyio
    async def test_get_json_object(self, mock_context):
        client = AsyncMock()
        client.get = AsyncMock(return_value=b'{"name": "Alice", "age": 30}')

        config = RedisKeyValueGetActionConfig(method="get", key="user:1")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["value"] == {"name": "Alice", "age": 30}

    @pytest.mark.anyio
    async def test_get_plain_string(self, mock_context):
        client = AsyncMock()
        client.get = AsyncMock(return_value=b"plain text")

        config = RedisKeyValueGetActionConfig(method="get", key="msg")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["value"] == "plain text"

    @pytest.mark.anyio
    async def test_set_string_no_ttl(self, mock_context):
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="k", value="v")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        client.set.assert_called_once_with("k", "v")
        registered = mock_context.register_source.call_args[0][1]
        assert registered["success"] is True

    @pytest.mark.anyio
    async def test_set_with_ttl(self, mock_context):
        client = AsyncMock()
        client.setex = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="k", value="v", ttl=60)
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        client.setex.assert_called_once_with("k", 60, "v")

    @pytest.mark.anyio
    async def test_set_dict_value_serialized(self, mock_context):
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        data = {"name": "Alice", "roles": ["admin"]}
        config = RedisKeyValueSetActionConfig(method="set", key="user", value=data)
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        call_args = client.set.call_args[0]
        assert call_args[0] == "user"
        assert json.loads(call_args[1]) == data

    @pytest.mark.anyio
    async def test_set_list_value_serialized(self, mock_context):
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        data = [1, 2, 3]
        config = RedisKeyValueSetActionConfig(method="set", key="nums", value=data)
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        call_args = client.set.call_args[0]
        assert json.loads(call_args[1]) == [1, 2, 3]

    @pytest.mark.anyio
    async def test_set_int_value_to_string(self, mock_context):
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)

        config = RedisKeyValueSetActionConfig(method="set", key="count", value=42)
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        call_args = client.set.call_args[0]
        assert call_args[1] == "42"

    @pytest.mark.anyio
    async def test_delete(self, mock_context):
        client = AsyncMock()
        client.delete = AsyncMock(return_value=1)

        config = RedisKeyValueDeleteActionConfig(method="delete", key="k")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        client.delete.assert_called_once_with("k")
        registered = mock_context.register_source.call_args[0][1]
        assert registered["count"] == 1

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, mock_context):
        client = AsyncMock()
        client.delete = AsyncMock(return_value=0)

        config = RedisKeyValueDeleteActionConfig(method="delete", key="missing")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["count"] == 0

    @pytest.mark.anyio
    async def test_exists_true(self, mock_context):
        client = AsyncMock()
        client.exists = AsyncMock(return_value=1)

        config = RedisKeyValueExistsActionConfig(method="exists", key="k")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["exists"] is True

    @pytest.mark.anyio
    async def test_exists_false(self, mock_context):
        client = AsyncMock()
        client.exists = AsyncMock(return_value=0)

        config = RedisKeyValueExistsActionConfig(method="exists", key="missing")
        action = RedisKeyValueStoreAction(config)
        result = await action.run(mock_context, client)

        registered = mock_context.register_source.call_args[0][1]
        assert registered["exists"] is False


# ──────────────────────────────────────────────
# Integration Tests (real Redis on localhost:6379)
# ──────────────────────────────────────────────

@pytest.fixture
async def redis_client():
    from redis.asyncio import Redis
    client = Redis.from_url("redis://localhost:6379/15")  # use DB 15 for tests
    yield client
    await client.flushdb()
    await client.close()


@pytest.fixture
def integration_context():
    context = ComponentActionContext(run_id="test-run", input={})
    return context


@pytest.mark.integration
class TestRedisKeyValueStoreIntegration:
    """Integration tests against a real Redis instance on localhost:6379."""

    @pytest.mark.anyio
    async def test_set_and_get_string(self, redis_client, integration_context):
        # SET
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:str", value="hello")
        set_action = RedisKeyValueStoreAction(set_config)
        set_result = await set_action.run(integration_context, redis_client)
        assert set_result["success"] is True

        # GET
        get_config = RedisKeyValueGetActionConfig(method="get", key="test:str")
        get_action = RedisKeyValueStoreAction(get_config)
        get_result = await get_action.run(integration_context, redis_client)
        assert get_result["value"] == "hello"

    @pytest.mark.anyio
    async def test_set_and_get_json_object(self, redis_client, integration_context):
        data = {"name": "Alice", "age": 30, "tags": ["admin", "user"]}

        set_config = RedisKeyValueSetActionConfig(method="set", key="test:json", value=data)
        set_action = RedisKeyValueStoreAction(set_config)
        await set_action.run(integration_context, redis_client)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:json")
        get_action = RedisKeyValueStoreAction(get_config)
        get_result = await get_action.run(integration_context, redis_client)
        assert get_result["value"] == data

    @pytest.mark.anyio
    async def test_set_with_ttl(self, redis_client, integration_context):
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:ttl", value="temp", ttl=10)
        set_action = RedisKeyValueStoreAction(set_config)
        await set_action.run(integration_context, redis_client)

        ttl = await redis_client.ttl("test:ttl")
        assert 0 < ttl <= 10

    @pytest.mark.anyio
    async def test_get_nonexistent_key(self, redis_client, integration_context):
        get_config = RedisKeyValueGetActionConfig(method="get", key="test:nonexistent")
        get_action = RedisKeyValueStoreAction(get_config)
        get_result = await get_action.run(integration_context, redis_client)
        assert get_result["value"] is None

    @pytest.mark.anyio
    async def test_delete(self, redis_client, integration_context):
        # Setup
        await redis_client.set("test:del", "value")

        # DELETE
        del_config = RedisKeyValueDeleteActionConfig(method="delete", key="test:del")
        del_action = RedisKeyValueStoreAction(del_config)
        del_result = await del_action.run(integration_context, redis_client)
        assert del_result["count"] == 1

        # Verify gone
        val = await redis_client.get("test:del")
        assert val is None

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, redis_client, integration_context):
        del_config = RedisKeyValueDeleteActionConfig(method="delete", key="test:nope")
        del_action = RedisKeyValueStoreAction(del_config)
        del_result = await del_action.run(integration_context, redis_client)
        assert del_result["count"] == 0

    @pytest.mark.anyio
    async def test_exists(self, redis_client, integration_context):
        await redis_client.set("test:exists", "yes")

        exists_config = RedisKeyValueExistsActionConfig(method="exists", key="test:exists")
        exists_action = RedisKeyValueStoreAction(exists_config)
        exists_result = await exists_action.run(integration_context, redis_client)
        assert exists_result["exists"] is True

    @pytest.mark.anyio
    async def test_not_exists(self, redis_client, integration_context):
        exists_config = RedisKeyValueExistsActionConfig(method="exists", key="test:nope")
        exists_action = RedisKeyValueStoreAction(exists_config)
        exists_result = await exists_action.run(integration_context, redis_client)
        assert exists_result["exists"] is False

    @pytest.mark.anyio
    async def test_overwrite_value(self, redis_client, integration_context):
        set_config1 = RedisKeyValueSetActionConfig(method="set", key="test:ow", value="first")
        await RedisKeyValueStoreAction(set_config1).run(integration_context, redis_client)

        set_config2 = RedisKeyValueSetActionConfig(method="set", key="test:ow", value="second")
        await RedisKeyValueStoreAction(set_config2).run(integration_context, redis_client)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:ow")
        get_result = await RedisKeyValueStoreAction(get_config).run(integration_context, redis_client)
        assert get_result["value"] == "second"

    @pytest.mark.anyio
    async def test_set_int_get_as_int(self, redis_client, integration_context):
        """int values stored as string, retrieved and JSON-parsed back to int."""
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:int", value=42)
        await RedisKeyValueStoreAction(set_config).run(integration_context, redis_client)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:int")
        get_result = await RedisKeyValueStoreAction(get_config).run(integration_context, redis_client)
        assert get_result["value"] == 42

    @pytest.mark.anyio
    async def test_set_bool_get_as_string(self, redis_client, integration_context):
        """bool stored as 'True'/'False' string, not valid JSON, returned as string."""
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:bool", value=True)
        await RedisKeyValueStoreAction(set_config).run(integration_context, redis_client)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:bool")
        get_result = await RedisKeyValueStoreAction(get_config).run(integration_context, redis_client)
        assert get_result["value"] == "True"

    @pytest.mark.anyio
    async def test_full_crud_cycle(self, redis_client, integration_context):
        key = "test:crud"

        # EXISTS -> False
        exists_result = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key=key)
        ).run(integration_context, redis_client)
        assert exists_result["exists"] is False

        # SET
        await RedisKeyValueStoreAction(
            RedisKeyValueSetActionConfig(method="set", key=key, value={"status": "active"})
        ).run(integration_context, redis_client)

        # EXISTS -> True
        exists_result = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key=key)
        ).run(integration_context, redis_client)
        assert exists_result["exists"] is True

        # GET
        get_result = await RedisKeyValueStoreAction(
            RedisKeyValueGetActionConfig(method="get", key=key)
        ).run(integration_context, redis_client)
        assert get_result["value"] == {"status": "active"}

        # DELETE
        del_result = await RedisKeyValueStoreAction(
            RedisKeyValueDeleteActionConfig(method="delete", key=key)
        ).run(integration_context, redis_client)
        assert del_result["count"] == 1

        # EXISTS -> False
        exists_result = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key=key)
        ).run(integration_context, redis_client)
        assert exists_result["exists"] is False
