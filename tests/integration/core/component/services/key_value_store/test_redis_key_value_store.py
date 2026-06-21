"""Live integration tests for the Redis key-value store against a real Redis on localhost:6379."""

import pytest

from mindor.dsl.schema.action import (
    RedisKeyValueGetActionConfig,
    RedisKeyValueSetActionConfig,
    RedisKeyValueDeleteActionConfig,
    RedisKeyValueExistsActionConfig,
)
from mindor.core.component.services.key_value_store.drivers.redis import (
    RedisKeyValueStoreAction,
)
from mindor.core.component.context import ComponentActionContext


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
async def redis_client():
    """Provide a Redis client connected to DB 15 for testing, flushed after use."""
    from redis.asyncio import Redis
    client = Redis.from_url("redis://localhost:6379/15")  # use DB 15 for tests
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def integration_context():
    """Provide a real ComponentActionContext for integration tests."""
    context = ComponentActionContext(run_id="test-run", input={})
    return context


class TestRedisKeyValueStoreIntegration:
    """Integration tests against a real Redis instance on localhost:6379."""

    @pytest.mark.anyio
    async def test_set_and_get_string(self, redis_client, integration_context):
        """Verify SET followed by GET round-trips a string value."""
        # SET
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:str", value="hello")
        set_action = RedisKeyValueStoreAction(set_config, redis_client)
        set_result = await set_action.run(integration_context)
        assert set_result["success"] is True

        # GET
        get_config = RedisKeyValueGetActionConfig(method="get", key="test:str")
        get_action = RedisKeyValueStoreAction(get_config, redis_client)
        get_result = await get_action.run(integration_context)
        assert get_result["value"] == "hello"

    @pytest.mark.anyio
    async def test_set_and_get_json_object(self, redis_client, integration_context):
        """Verify SET followed by GET round-trips a JSON object."""
        data = {"name": "Alice", "age": 30, "tags": ["admin", "user"]}

        set_config = RedisKeyValueSetActionConfig(method="set", key="test:json", value=data)
        set_action = RedisKeyValueStoreAction(set_config, redis_client)
        await set_action.run(integration_context)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:json")
        get_action = RedisKeyValueStoreAction(get_config, redis_client)
        get_result = await get_action.run(integration_context)
        assert get_result["value"] == data

    @pytest.mark.anyio
    async def test_set_with_ttl(self, redis_client, integration_context):
        """Verify SET with TTL applies an expiry to the key."""
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:ttl", value="temp", ttl=10)
        set_action = RedisKeyValueStoreAction(set_config, redis_client)
        await set_action.run(integration_context)

        ttl = await redis_client.ttl("test:ttl")
        assert 0 < ttl <= 10

    @pytest.mark.anyio
    async def test_get_nonexistent_key(self, redis_client, integration_context):
        """Verify GET returns None for a key that does not exist."""
        get_config = RedisKeyValueGetActionConfig(method="get", key="test:nonexistent")
        get_action = RedisKeyValueStoreAction(get_config, redis_client)
        get_result = await get_action.run(integration_context)
        assert get_result["value"] is None

    @pytest.mark.anyio
    async def test_delete(self, redis_client, integration_context):
        """Verify DELETE removes an existing key."""
        # Setup
        await redis_client.set("test:del", "value")

        # DELETE
        del_config = RedisKeyValueDeleteActionConfig(method="delete", key="test:del")
        del_action = RedisKeyValueStoreAction(del_config, redis_client)
        del_result = await del_action.run(integration_context)
        assert del_result["count"] == 1

        # Verify gone
        val = await redis_client.get("test:del")
        assert val is None

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, redis_client, integration_context):
        """Verify DELETE on a nonexistent key returns count 0."""
        del_config = RedisKeyValueDeleteActionConfig(method="delete", key="test:nope")
        del_action = RedisKeyValueStoreAction(del_config, redis_client)
        del_result = await del_action.run(integration_context)
        assert del_result["count"] == 0

    @pytest.mark.anyio
    async def test_exists(self, redis_client, integration_context):
        """Verify EXISTS returns True for a key that exists."""
        await redis_client.set("test:exists", "yes")

        exists_config = RedisKeyValueExistsActionConfig(method="exists", key="test:exists")
        exists_action = RedisKeyValueStoreAction(exists_config, redis_client)
        exists_result = await exists_action.run(integration_context)
        assert exists_result["exists"] is True

    @pytest.mark.anyio
    async def test_not_exists(self, redis_client, integration_context):
        """Verify EXISTS returns False for a key that does not exist."""
        exists_config = RedisKeyValueExistsActionConfig(method="exists", key="test:nope")
        exists_action = RedisKeyValueStoreAction(exists_config, redis_client)
        exists_result = await exists_action.run(integration_context)
        assert exists_result["exists"] is False

    @pytest.mark.anyio
    async def test_overwrite_value(self, redis_client, integration_context):
        """Verify SET overwrites a previously stored value."""
        set_config1 = RedisKeyValueSetActionConfig(method="set", key="test:ow", value="first")
        await RedisKeyValueStoreAction(set_config1, redis_client).run(integration_context)

        set_config2 = RedisKeyValueSetActionConfig(method="set", key="test:ow", value="second")
        await RedisKeyValueStoreAction(set_config2, redis_client).run(integration_context)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:ow")
        get_result = await RedisKeyValueStoreAction(get_config, redis_client).run(integration_context)
        assert get_result["value"] == "second"

    @pytest.mark.anyio
    async def test_set_int_get_as_int(self, redis_client, integration_context):
        """int values stored as string, retrieved and JSON-parsed back to int."""
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:int", value=42)
        await RedisKeyValueStoreAction(set_config, redis_client).run(integration_context)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:int")
        get_result = await RedisKeyValueStoreAction(get_config, redis_client).run(integration_context)
        assert get_result["value"] == 42

    @pytest.mark.anyio
    async def test_set_bool_get_as_string(self, redis_client, integration_context):
        """bool stored as 'True'/'False' string, not valid JSON, returned as string."""
        set_config = RedisKeyValueSetActionConfig(method="set", key="test:bool", value=True)
        await RedisKeyValueStoreAction(set_config, redis_client).run(integration_context)

        get_config = RedisKeyValueGetActionConfig(method="get", key="test:bool")
        get_result = await RedisKeyValueStoreAction(get_config, redis_client).run(integration_context)
        assert get_result["value"] == "True"

    @pytest.mark.anyio
    async def test_full_crud_cycle(self, redis_client, integration_context):
        """Verify a full CRUD cycle: exists, set, exists, get, delete, exists."""
        key = "test:crud"

        # EXISTS -> False
        exists_result = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key=key),
            redis_client,
        ).run(integration_context)
        assert exists_result["exists"] is False

        # SET
        await RedisKeyValueStoreAction(
            RedisKeyValueSetActionConfig(method="set", key=key, value={"status": "active"}),
            redis_client,
        ).run(integration_context)

        # EXISTS -> True
        exists_result = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key=key),
            redis_client,
        ).run(integration_context)
        assert exists_result["exists"] is True

        # GET
        get_result = await RedisKeyValueStoreAction(
            RedisKeyValueGetActionConfig(method="get", key=key),
            redis_client,
        ).run(integration_context)
        assert get_result["value"] == {"status": "active"}

        # DELETE
        del_result = await RedisKeyValueStoreAction(
            RedisKeyValueDeleteActionConfig(method="delete", key=key),
            redis_client,
        ).run(integration_context)
        assert del_result["count"] == 1

        # EXISTS -> False
        exists_result = await RedisKeyValueStoreAction(
            RedisKeyValueExistsActionConfig(method="exists", key=key),
            redis_client,
        ).run(integration_context)
        assert exists_result["exists"] is False
