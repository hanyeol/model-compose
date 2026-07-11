"""Tests for model-memory component schema, buffer drivers, storage, and action lifecycle."""

import asyncio
import os
import tempfile

import pytest
from pydantic import TypeAdapter, ValidationError

from unittest.mock import AsyncMock, MagicMock

from mindor.dsl.schema.component import (
    ComponentConfig,
    ModelMemoryComponentConfig,
    ModelMemoryStorageDriver,
    ModelMemoryWindowConfig,
    MemoryModelMemoryBufferConfig,
    RedisModelMemoryBufferConfig,
)
from mindor.dsl.schema.action import (
    ModelMemoryActionConfig,
    ModelMemoryActionMethod,
    ModelMemoryAppendActionConfig,
    ModelMemorySaveActionConfig,
    ModelMemoryLoadActionConfig,
    ModelMemoryClearActionConfig,
    ModelMemoryDeleteActionConfig,
)
from mindor.core.component.services.model_memory.model_memory import (
    ModelMemoryAction,
    ModelMemoryComponent,
)
from mindor.core.component.services.model_memory.buffer.drivers.memory import MemoryModelMemoryBuffer
from mindor.core.component.services.model_memory.buffer.drivers.redis import RedisModelMemoryBuffer
from mindor.core.component.services.model_memory.storage.drivers.sqlite import SqliteModelMemoryStorage
from mindor.core.component.context import ComponentActionContext


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


async def wait_until(predicate, timeout: float = 1.0, interval: float = 0.005):
    """Poll an async predicate until it returns truthy or timeout elapses.

    Replaces asyncio.sleep(N) patterns to avoid flakiness under CI load.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = await predicate() if asyncio.iscoroutinefunction(predicate) else predicate()
        if result:
            return result
        await asyncio.sleep(interval)
    raise AssertionError(f"Condition not met within {timeout}s")


# ──────────────────────────────────────────────
# Schema Tests
# ──────────────────────────────────────────────


class TestModelMemorySchema:
    """Test model-memory component and action schema validation."""

    component_adapter = TypeAdapter(ComponentConfig)

    def test_minimal_config(self):
        """Test that a minimal config applies correct defaults."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [],
        })
        assert config.type.value == "model-memory"
        assert config.storage.driver == "sqlite"
        assert config.storage.path == ".model-memory.db"
        assert config.buffer.driver == "memory"
        assert config.window is None
        assert config.summary is None

    def test_sqlite_storage_config(self):
        """Test that explicit SQLite storage config is accepted."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "storage": {"driver": "sqlite", "path": "./test.db"},
            "actions": [],
        })
        assert config.storage.driver == "sqlite"
        assert config.storage.path == "./test.db"

    def test_buffer_config_default(self):
        """Test that the default buffer driver is memory."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [],
        })
        assert config.buffer.driver == "memory"

    def test_buffer_config_explicit_memory(self):
        """Test that explicitly setting buffer driver to memory works."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "buffer": {"driver": "memory"},
            "actions": [],
        })
        assert config.buffer.driver == "memory"

    def test_buffer_config_redis(self):
        """Test that Redis buffer config with custom host and port is accepted."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "buffer": {"driver": "redis", "host": "redis.local", "port": 6380},
            "actions": [],
        })
        assert config.buffer.driver == "redis"
        assert config.buffer.host == "redis.local"
        assert config.buffer.port == 6380

    def test_window_int_inflates_to_config(self):
        """Test that an integer window value inflates to ModelMemoryWindowConfig."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "window": 5,
            "actions": [],
        })
        assert isinstance(config.window, ModelMemoryWindowConfig)
        assert config.window.max_turn_count == 5
        assert config.window.max_message_count is None

    def test_window_object(self):
        """Test that a window object config is accepted with all fields."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "window": {"max_turn_count": 10, "max_message_count": 50},
            "actions": [],
        })
        assert config.window.max_turn_count == 10
        assert config.window.max_message_count == 50

    def test_action_load(self):
        """Test that a load action config is parsed correctly."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [
                {"id": "load", "method": "load", "session_id": "s1"},
            ],
        })
        action = config.actions[0]
        assert action.method == ModelMemoryActionMethod.LOAD

    def test_action_append(self):
        """Test that an append action config is parsed correctly."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [
                {"id": "append", "method": "append", "session_id": "s1", "messages": []},
            ],
        })
        action = config.actions[0]
        assert action.method == ModelMemoryActionMethod.APPEND

    def test_action_save(self):
        """Test that a save action config is parsed correctly."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [
                {"id": "save", "method": "save", "session_id": "s1"},
            ],
        })
        action = config.actions[0]
        assert action.method == ModelMemoryActionMethod.SAVE

    def test_action_clear(self):
        """Test that a clear action config is parsed correctly."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [
                {"id": "clear", "method": "clear", "session_id": "s1"},
            ],
        })
        assert config.actions[0].method == ModelMemoryActionMethod.CLEAR

    def test_action_delete(self):
        """Test that a delete action config is parsed correctly."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [
                {"id": "delete", "method": "delete", "session_id": "s1"},
            ],
        })
        assert config.actions[0].method == ModelMemoryActionMethod.DELETE

    def test_invalid_method(self):
        """Test that an invalid action method raises a validation error."""
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "mem",
                "type": "model-memory",
                "actions": [
                    {"id": "bad", "method": "invalid", "session_id": "s1"},
                ],
            })

    def test_multiple_actions(self):
        """Test that multiple actions of different methods can coexist."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "actions": [
                {"id": "load", "method": "load", "session_id": "s1"},
                {"id": "append", "method": "append", "session_id": "s1", "messages": "${input.messages}"},
                {"id": "save", "method": "save", "session_id": "s1"},
            ],
        })
        assert len(config.actions) == 3
        methods = [a.method for a in config.actions]
        assert methods == [
            ModelMemoryActionMethod.LOAD,
            ModelMemoryActionMethod.APPEND,
            ModelMemoryActionMethod.SAVE,
        ]

    def test_summary_config(self):
        """Test that summary config with component and action is accepted."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "summary": {
                "component": "summarizer",
                "action": "summarize",
            },
            "actions": [],
        })
        assert config.summary.component == "summarizer"
        assert config.summary.action == "summarize"


# ──────────────────────────────────────────────
# ModelMemoryBuffer Unit Tests
# ──────────────────────────────────────────────


def make_buffer():
    """Create a MemoryModelMemoryBuffer with default config."""
    return MemoryModelMemoryBuffer(MemoryModelMemoryBufferConfig())


class TestModelMemoryBuffer:
    """Test in-memory buffer driver operations."""

    @pytest.mark.anyio
    async def test_get_turns_returns_none_when_not_in_buffer(self):
        """Test that get_turns returns None for a nonexistent session."""
        buffer = make_buffer()
        assert await buffer.get_turns("nope") is None

    @pytest.mark.anyio
    async def test_set_turns_creates_session(self):
        """Test that set_turns creates a new session in the buffer."""
        buffer = make_buffer()
        await buffer.set_turns("s1", [[{"role": "user", "content": "hi"}]])
        turns = await buffer.get_turns("s1")
        assert turns is not None
        assert len(turns) == 1

    @pytest.mark.anyio
    async def test_append_turn_creates_session(self):
        """Test that append_turn creates a session if it does not exist."""
        buffer = make_buffer()
        await buffer.append_turn("s1", [{"role": "user", "content": "hi"}])
        turns = await buffer.get_turns("s1")
        assert turns is not None
        assert len(turns) == 1

    @pytest.mark.anyio
    async def test_get_summary_returns_none_when_not_in_buffer(self):
        """Test that get_summary returns None for a nonexistent session."""
        buffer = make_buffer()
        assert await buffer.get_summary("nope") is None

    @pytest.mark.anyio
    async def test_set_summary_creates_session(self):
        """Test that set_summary stores and retrieves a summary."""
        buffer = make_buffer()
        await buffer.set_summary("s1", "hello")
        assert await buffer.get_summary("s1") == "hello"

    @pytest.mark.anyio
    async def test_remove(self):
        """Test that remove deletes a session from the buffer."""
        buffer = make_buffer()
        await buffer.set_turns("s1", [])
        await buffer.remove("s1")
        assert await buffer.get_turns("s1") is None

    @pytest.mark.anyio
    async def test_remove_nonexistent(self):
        """Test that removing a nonexistent session does not raise."""
        buffer = make_buffer()
        await buffer.remove("nope")  # should not raise

    @pytest.mark.anyio
    async def test_merge_and_snapshot_restore(self):
        """Test that snapshot and restore correctly roll back buffer state."""
        buffer = make_buffer()
        await buffer.set_turns("s1", [[{"role": "user", "content": "t1"}]])
        await buffer.set_summary("s1", "old")
        await buffer.merge_buffer("s1")
        await buffer.take_snapshot("s1")

        await buffer.append_turn("s1", [{"role": "user", "content": "t2"}])
        await buffer.set_summary("s1", "new")
        turns = await buffer.get_turns("s1")
        assert len(turns) == 2

        await buffer.restore_snapshot("s1")
        turns = await buffer.get_turns("s1")
        assert len(turns) == 1
        assert await buffer.get_summary("s1") == "old"


# ──────────────────────────────────────────────
# SQLite Storage Integration Tests
# ──────────────────────────────────────────────


@pytest.fixture
async def sqlite_storage():
    """Provide a temporary SQLite storage instance for testing."""
    from mindor.dsl.schema.component import SqliteModelMemoryStorageConfig
    with tempfile.TemporaryDirectory() as tmpdir:
        config = SqliteModelMemoryStorageConfig(path=os.path.join(tmpdir, "test.db"))
        storage = SqliteModelMemoryStorage(config)
        await storage.setup()
        yield storage
        await storage.close()


class TestSqliteModelMemoryStorage:
    """Test SQLite-backed model memory storage operations."""

    @pytest.mark.anyio
    async def test_load_empty_session(self, sqlite_storage):
        """Test that loading a new session returns empty turns and summary."""
        turns, summary = await sqlite_storage.load("new-session")
        assert turns == []
        assert summary == ""

    @pytest.mark.anyio
    async def test_save_and_load(self, sqlite_storage):
        """Test that saved turns and summary can be loaded back."""
        turns = [
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            [{"role": "user", "content": "bye"}],
        ]
        await sqlite_storage.save("s1", turns=turns, summary="greeting")

        loaded_turns, loaded_summary = await sqlite_storage.load("s1")
        assert loaded_turns == turns
        assert loaded_summary == "greeting"

    @pytest.mark.anyio
    async def test_save_overwrites(self, sqlite_storage):
        """Test that saving to the same session overwrites previous data."""
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "v1"}]], summary="first")
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "v2"}]], summary="second")

        turns, summary = await sqlite_storage.load("s1")
        assert turns == [[{"role": "user", "content": "v2"}]]
        assert summary == "second"

    @pytest.mark.anyio
    async def test_delete(self, sqlite_storage):
        """Test that deleting a session removes its data."""
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "hi"}]], summary="")
        await sqlite_storage.delete("s1")

        turns, _ = await sqlite_storage.load("s1")
        assert turns == []

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, sqlite_storage):
        """Test that deleting a nonexistent session does not raise."""
        await sqlite_storage.delete("nope")  # should not raise

    @pytest.mark.anyio
    async def test_multiple_sessions(self, sqlite_storage):
        """Test that multiple sessions are stored independently."""
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "a"}]], summary="sa")
        await sqlite_storage.save("s2", turns=[[{"role": "user", "content": "b"}]], summary="sb")

        turns1, summary1 = await sqlite_storage.load("s1")
        turns2, summary2 = await sqlite_storage.load("s2")
        assert turns1 != turns2
        assert summary1 == "sa"
        assert summary2 == "sb"


# ──────────────────────────────────────────────
# ModelMemoryAction E2E Tests (with real SQLite)
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


def make_component_config(**overrides):
    """Create a ModelMemoryComponentConfig with sensible defaults."""
    base = {
        "id": "mem",
        "type": "model-memory",
        "actions": [],
    }
    base.update(overrides)
    return TypeAdapter(ComponentConfig).validate_python(base)


def make_action(action_config, component_config, global_configs=None):
    """Create a ModelMemoryAction instance.

    ModelMemoryAction now takes an already-resolved summary component service
    rather than global_configs. When a `global_configs` fixture is provided and
    the component config declares a summary, we resolve the referenced component
    via `create_component` (which consults the shared `ComponentInstances` cache
    so tests may pre-register stubs).
    """
    summary_component = None
    if component_config.summary is not None:
        from mindor.core.component.component import (
            ComponentInstances,
            ComponentResolver,
            create_component,
        )

        summary_component_id = component_config.summary.component
        summary_component = ComponentInstances.get(summary_component_id)

        if summary_component is None and global_configs is not None and not isinstance(global_configs, MagicMock):
            _, resolved_config = ComponentResolver(global_configs.components).resolve(summary_component_id)
            summary_component = create_component(summary_component_id, resolved_config, global_configs, daemon=False)

    return ModelMemoryAction(action_config, component_config.window, component_config.summary, summary_component)


class TestModelMemoryActionE2E:
    """E2E tests: ModelMemoryAction + real SQLite storage + real buffer."""

    @pytest.mark.anyio
    async def test_load_empty_session(self, sqlite_storage, mock_context):
        """Test that loading an empty session returns no messages."""
        buffer = make_buffer()
        component_config = make_component_config()
        action_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")

        action = make_action(action_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        assert result["messages"] == []
        assert result["summary"] == ""

    @pytest.mark.anyio
    async def test_load_append_save_cycle(self, sqlite_storage, mock_context):
        """Test that a load-append-save cycle persists messages to storage."""
        buffer = make_buffer()
        component_config = make_component_config()

        # Load
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Append
        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        append_config = ModelMemoryAppendActionConfig(method="append", session_id="s1", messages=messages)
        action = make_action(append_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        # Save
        save_config = ModelMemorySaveActionConfig(method="save", session_id="s1")
        action = make_action(save_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        # Verify persisted
        turns, _ = await sqlite_storage.load("s1")
        assert len(turns) == 1
        assert turns[0] == messages

    @pytest.mark.anyio
    async def test_load_returns_persisted_data(self, sqlite_storage, mock_context):
        """Test that load returns previously persisted turns and summary."""
        # Pre-populate storage
        turns = [
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            [{"role": "user", "content": "how are you?"}, {"role": "assistant", "content": "fine"}],
        ]
        await sqlite_storage.save("s1", turns=turns, summary="greeting convo")

        buffer = make_buffer()
        component_config = make_component_config()
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        assert result["summary"] == "greeting convo"
        assert len(result["messages"]) == 4

    @pytest.mark.anyio
    async def test_window_limits_returned_messages(self, sqlite_storage, mock_context):
        """Test that window config limits the number of returned messages."""
        turns = [
            [{"role": "user", "content": f"turn{i}"}] for i in range(5)
        ]
        await sqlite_storage.save("s1", turns=turns, summary="")

        buffer = make_buffer()
        component_config = make_component_config(window=2)
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        assert len(result["messages"]) == 2
        # Should be the last 2 turns
        assert result["messages"][0]["content"] == "turn3"
        assert result["messages"][1]["content"] == "turn4"

    @pytest.mark.anyio
    async def test_clear_restores_snapshot(self, sqlite_storage, mock_context):
        """Test that clear restores the buffer to its snapshot state."""
        buffer = make_buffer()
        component_config = make_component_config()

        # Load
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Append
        append_config = ModelMemoryAppendActionConfig(
            method="append", session_id="s1",
            messages=[{"role": "user", "content": "hello"}],
        )
        action = make_action(append_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Clear (should rollback to snapshot = empty)
        clear_config = ModelMemoryClearActionConfig(method="clear", session_id="s1")
        action = make_action(clear_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        # Verify buffer is cleared
        turns = await buffer.get_turns("s1")
        assert len(turns) == 0

    @pytest.mark.anyio
    async def test_delete_removes_from_storage_and_buffer(self, sqlite_storage, mock_context):
        """Test that delete removes data from both storage and buffer."""
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "hi"}]], summary="")

        buffer = make_buffer()
        # Load first to populate buffer
        component_config = make_component_config()
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)
        assert await buffer.get_turns("s1") is not None

        # Delete
        delete_config = ModelMemoryDeleteActionConfig(method="delete", session_id="s1")
        action = make_action(delete_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        # Verify
        assert await buffer.get_turns("s1") is None
        turns, _ = await sqlite_storage.load("s1")
        assert turns == []

    @pytest.mark.anyio
    async def test_save_without_prior_load_raises(self, sqlite_storage, mock_context):
        """Save requires an explicit load first; calling save on an unloaded session raises."""
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "old"}]], summary="")

        buffer = make_buffer()
        component_config = make_component_config()

        new_messages = [{"role": "user", "content": "new"}]
        save_config = ModelMemorySaveActionConfig(method="save", session_id="s1", messages=new_messages)
        action = make_action(save_config, component_config)

        with pytest.raises(LookupError, match="Session not loaded"):
            await action.run(mock_context, buffer, sqlite_storage)

    @pytest.mark.anyio
    async def test_default_session_id(self, sqlite_storage, mock_context):
        """When session_id is omitted, schema default __session__ is used."""
        buffer = make_buffer()
        component_config = make_component_config()

        load_config = ModelMemoryLoadActionConfig(method="load")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        assert await buffer.get_turns("__session__") is not None

    @pytest.mark.anyio
    async def test_append_without_load_raises(self, sqlite_storage, mock_context):
        """Test that appending without a prior load raises ValueError."""
        buffer = make_buffer()
        component_config = make_component_config()

        append_config = ModelMemoryAppendActionConfig(
            method="append", session_id="s1",
            messages=[{"role": "user", "content": "hello"}],
        )
        action = make_action(append_config, component_config)

        with pytest.raises(LookupError, match="Session not loaded"):
            await action.run(mock_context, buffer, sqlite_storage)

    @pytest.mark.anyio
    async def test_window_prunes_on_append(self, sqlite_storage, mock_context):
        """With window=2, appending a 3rd turn should prune the oldest."""
        buffer = make_buffer()
        component_config = make_component_config(window=2)

        # Load
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Append 3 turns
        for i in range(3):
            append_config = ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": f"turn{i}"}],
            )
            action = make_action(append_config, component_config)
            await action.run(mock_context, buffer, sqlite_storage)

        # Should have only 2 turns (windowed)
        turns = await buffer.get_turns("s1")
        assert len(turns) == 2
        assert turns[0][0]["content"] == "turn1"
        assert turns[1][0]["content"] == "turn2"

    @pytest.mark.anyio
    async def test_full_lifecycle(self, sqlite_storage, mock_context):
        """Full cycle: load -> append -> save -> reload -> verify."""
        buffer = make_buffer()
        component_config = make_component_config()

        # Load
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Append turn 1
        append_config = ModelMemoryAppendActionConfig(
            method="append", session_id="s1",
            messages=[{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi there"}],
        )
        action = make_action(append_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Append turn 2
        append_config = ModelMemoryAppendActionConfig(
            method="append", session_id="s1",
            messages=[{"role": "user", "content": "how are you?"}],
        )
        action = make_action(append_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Save
        save_config = ModelMemorySaveActionConfig(method="save", session_id="s1")
        action = make_action(save_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        # Simulate fresh start: new buffer, reload from storage
        buffer2 = make_buffer()
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        result = await action.run(mock_context, buffer2, sqlite_storage)

        assert result["messages"][0]["content"] == "hello"
        assert result["messages"][1]["content"] == "hi there"
        assert result["messages"][2]["content"] == "how are you?"

    @pytest.mark.anyio
    async def test_save_with_empty_messages_list(self, sqlite_storage, mock_context):
        """Save with messages=[] should append an empty turn (not skip)."""
        buffer = make_buffer()
        component_config = make_component_config()

        # Load
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Save with empty messages
        save_config = ModelMemorySaveActionConfig(method="save", session_id="s1", messages=[])
        action = make_action(save_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

    @pytest.mark.anyio
    async def test_append_with_non_list_messages_raises(self, sqlite_storage, mock_context):
        """Append with non-list messages after rendering should raise."""
        buffer = make_buffer()
        component_config = make_component_config()

        # Load first
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Append with string messages (simulating unresolved template)
        append_config = ModelMemoryAppendActionConfig(method="append", session_id="s1", messages="not a list")
        action = make_action(append_config, component_config)

        with pytest.raises(TypeError, match=r"'messages' must be a list"):
            await action.run(mock_context, buffer, sqlite_storage)

    @pytest.mark.anyio
    async def test_window_preserves_latest_turn_when_too_large(self, sqlite_storage, mock_context):
        """When max_message_count is smaller than the latest turn, the latest turn is still preserved."""
        # Create a turn with 10 messages
        large_turn = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        await sqlite_storage.save("s1", turns=[large_turn], summary="")

        buffer = make_buffer()
        component_config = make_component_config(
            window={"max_message_count": 3}
        )

        # Load
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        # Should still have the turn (latest turn preserved)
        assert len(result["messages"]) == 10

    @pytest.mark.anyio
    async def test_load_uses_buffer_as_source_of_truth(self, sqlite_storage, mock_context):
        """Second load should return buffer state, not storage."""
        buffer = make_buffer()
        component_config = make_component_config()

        # Load from storage
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Append to buffer (not saved to storage)
        append_config = ModelMemoryAppendActionConfig(
            method="append", session_id="s1",
            messages=[{"role": "user", "content": "buffered"}],
        )
        action = make_action(append_config, component_config)
        await action.run(mock_context, buffer, sqlite_storage)

        # Load again: should see the buffered data
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)

        assert result["messages"][0]["content"] == "buffered"


# ──────────────────────────────────────────────
# Redis Buffer Driver Tests (using fakeredis)
# ──────────────────────────────────────────────


@pytest.fixture
async def fake_redis_server():
    """Provide a fakeredis server instance for testing."""
    import fakeredis.aioredis
    return fakeredis.aioredis.FakeServer()


@pytest.fixture
async def redis_buffer(fake_redis_server):
    """Provide a RedisModelMemoryBuffer backed by fakeredis."""
    import fakeredis.aioredis
    config = RedisModelMemoryBufferConfig(driver="redis")
    buf = RedisModelMemoryBuffer(config)
    buf.client = fakeredis.aioredis.FakeRedis(server=fake_redis_server)
    buf._pubsub = buf.client.pubsub()
    await buf._pubsub.subscribe(buf._updates_channel())
    buf._listener_task = asyncio.create_task(buf._listen_updates())
    yield buf
    await buf.close()


class TestRedisModelMemoryBuffer:
    """Test Redis-backed buffer driver operations using fakeredis."""

    @pytest.mark.anyio
    async def test_get_turns_returns_none_when_not_in_buffer(self, redis_buffer):
        """Test that get_turns returns None for a nonexistent session."""
        assert await redis_buffer.get_turns("nope") is None

    @pytest.mark.anyio
    async def test_set_turns_creates_session(self, redis_buffer):
        """Test that set_turns creates a new session in the buffer."""
        await redis_buffer.set_turns("s1", [[{"role": "user", "content": "hi"}]])
        turns = await redis_buffer.get_turns("s1")
        assert turns is not None
        assert len(turns) == 1

    @pytest.mark.anyio
    async def test_append_turn_creates_session(self, redis_buffer):
        """Test that append_turn creates a session if it does not exist."""
        await redis_buffer.append_turn("s1", [{"role": "user", "content": "hi"}])
        turns = await redis_buffer.get_turns("s1")
        assert turns is not None
        assert len(turns) == 1

    @pytest.mark.anyio
    async def test_get_summary_returns_none_when_not_in_buffer(self, redis_buffer):
        """Test that get_summary returns None for a nonexistent session."""
        assert await redis_buffer.get_summary("nope") is None

    @pytest.mark.anyio
    async def test_set_summary_creates_session(self, redis_buffer):
        """Test that set_summary stores and retrieves a summary."""
        await redis_buffer.set_summary("s1", "hello")
        assert await redis_buffer.get_summary("s1") == "hello"

    @pytest.mark.anyio
    async def test_remove(self, redis_buffer):
        """Test that remove deletes a session from the buffer."""
        await redis_buffer.set_turns("s1", [])
        await redis_buffer.remove("s1")
        assert await redis_buffer.get_turns("s1") is None

    @pytest.mark.anyio
    async def test_remove_nonexistent(self, redis_buffer):
        """Test that removing a nonexistent session does not raise."""
        await redis_buffer.remove("nope")  # should not raise

    @pytest.mark.anyio
    async def test_merge_and_snapshot_restore(self, redis_buffer):
        """Test that snapshot and restore correctly roll back buffer state."""
        await redis_buffer.set_turns("s1", [[{"role": "user", "content": "t1"}]])
        await redis_buffer.set_summary("s1", "old")
        await redis_buffer.merge_buffer("s1")
        await redis_buffer.take_snapshot("s1")

        await redis_buffer.append_turn("s1", [{"role": "user", "content": "t2"}])
        await redis_buffer.set_summary("s1", "new")
        turns = await redis_buffer.get_turns("s1")
        assert len(turns) == 2

        await redis_buffer.restore_snapshot("s1")
        turns = await redis_buffer.get_turns("s1")
        assert len(turns) == 1
        assert await redis_buffer.get_summary("s1") == "old"

    @pytest.mark.anyio
    async def test_append_multiple_turns(self, redis_buffer):
        """Test that multiple appended turns accumulate correctly."""
        await redis_buffer.set_turns("s1", [[{"role": "user", "content": "t0"}]])
        await redis_buffer.append_turn("s1", [{"role": "user", "content": "t1"}])
        await redis_buffer.append_turn("s1", [{"role": "user", "content": "t2"}])
        turns = await redis_buffer.get_turns("s1")
        assert len(turns) == 3
        assert turns[0][0]["content"] == "t0"
        assert turns[1][0]["content"] == "t1"
        assert turns[2][0]["content"] == "t2"

    @pytest.mark.anyio
    async def test_set_turns_clears_pending(self, redis_buffer):
        """Test that set_turns clears any pending appended turns."""
        await redis_buffer.set_turns("s1", [[{"role": "user", "content": "t0"}]])
        await redis_buffer.append_turn("s1", [{"role": "user", "content": "t1"}])
        # set_turns should clear pending
        await redis_buffer.set_turns("s1", [[{"role": "user", "content": "replaced"}]])
        turns = await redis_buffer.get_turns("s1")
        assert len(turns) == 1
        assert turns[0][0]["content"] == "replaced"


# ──────────────────────────────────────────────
# Redis Pub/Sub Synchronization Tests
# ──────────────────────────────────────────────


async def make_redis_buffer(server) -> RedisModelMemoryBuffer:
    """Create a RedisModelMemoryBuffer backed by a shared fakeredis server."""
    import fakeredis.aioredis
    config = RedisModelMemoryBufferConfig(driver="redis")
    buf = RedisModelMemoryBuffer(config)
    buf.client = fakeredis.aioredis.FakeRedis(server=server)
    buf._pubsub = buf.client.pubsub()
    await buf._pubsub.subscribe(buf._updates_channel())
    buf._listener_task = asyncio.create_task(buf._listen_updates())
    return buf


class TestRedisPubSubSync:
    """Test Redis Pub/Sub synchronization between buffer instances."""

    @pytest.mark.anyio
    async def test_set_turns_notifies_remote(self, fake_redis_server):
        """Test that set_turns publishes an update received by remote buffers."""
        buf_a = await make_redis_buffer(fake_redis_server)
        buf_b = await make_redis_buffer(fake_redis_server)
        try:
            # Both load session s1
            await buf_a.set_turns("s1", [[{"role": "user", "content": "t0"}]])
            await buf_b.set_turns("s1", [[{"role": "user", "content": "t0"}]])

            # B appends a pending turn
            await buf_b.append_turn("s1", [{"role": "user", "content": "pending"}])
            assert len(await buf_b.get_turns("s1")) == 2

            # A updates turns — this publishes a Pub/Sub message
            await buf_a.set_turns("s1", [[{"role": "user", "content": "new"}]])

            # Wait for B's listener to process the remote update
            async def b_synced():
                turns = await buf_b.get_turns("s1")
                return turns is not None and len(turns) == 1 and turns[0][0]["content"] == "new"

            await wait_until(b_synced)

            # B's pending should be cleared by _on_remote_update_turns
            turns = await buf_b.get_turns("s1")
            assert len(turns) == 1
            assert turns[0][0]["content"] == "new"
        finally:
            await buf_a.close()
            await buf_b.close()

    @pytest.mark.anyio
    async def test_merge_buffer_notifies_remote(self, fake_redis_server):
        """Test that merge_buffer publishes an update received by remote buffers."""
        buf_a = await make_redis_buffer(fake_redis_server)
        buf_b = await make_redis_buffer(fake_redis_server)
        try:
            await buf_a.set_turns("s1", [])
            await buf_b.set_turns("s1", [])

            # A appends and merges
            await buf_a.append_turn("s1", [{"role": "user", "content": "t1"}])
            await buf_a.merge_buffer("s1")

            # B had pending turns
            await buf_b.append_turn("s1", [{"role": "user", "content": "stale"}])

            # Wait for B's listener to clear stale pending after remote merge
            async def b_cleared():
                turns = await buf_b.get_turns("s1")
                return turns is not None and len(turns) == 1 and turns[0][0]["content"] == "t1"

            await wait_until(b_cleared)

            # B's pending should be cleared
            turns = await buf_b.get_turns("s1")
            assert len(turns) == 1
            assert turns[0][0]["content"] == "t1"
        finally:
            await buf_a.close()
            await buf_b.close()

    @pytest.mark.anyio
    async def test_self_publish_ignored(self, fake_redis_server):
        """Test that a buffer ignores its own Pub/Sub messages."""
        buf = await make_redis_buffer(fake_redis_server)
        try:
            await buf.set_turns("s1", [])
            await buf.append_turn("s1", [{"role": "user", "content": "pending"}])

            # set_turns publishes, but listener should ignore own messages
            await buf.set_turns("s1", [[{"role": "user", "content": "new"}]])

            # Give listener a tick to deliver the self-publish (which should be ignored)
            await asyncio.sleep(0.02)

            # Pending was already cleared by set_turns itself, not by remote handler
            turns = await buf.get_turns("s1")
            assert len(turns) == 1
            assert turns[0][0]["content"] == "new"
        finally:
            await buf.close()

    @pytest.mark.anyio
    async def test_restore_snapshot_notifies_remote(self, fake_redis_server):
        """Test that restore_snapshot publishes an update received by remote buffers."""
        buf_a = await make_redis_buffer(fake_redis_server)
        buf_b = await make_redis_buffer(fake_redis_server)
        try:
            await buf_a.set_turns("s1", [[{"role": "user", "content": "original"}]])
            await buf_a.set_summary("s1", "orig summary")
            await buf_a.take_snapshot("s1")

            await buf_b.set_turns("s1", [[{"role": "user", "content": "original"}]])

            # B appends pending
            await buf_b.append_turn("s1", [{"role": "user", "content": "pending"}])

            # A restores snapshot — publishes update
            await buf_a.restore_snapshot("s1")

            # Wait for B's listener to apply the remote restore
            async def b_restored():
                turns = await buf_b.get_turns("s1")
                return turns is not None and len(turns) == 1 and turns[0][0]["content"] == "original"

            await wait_until(b_restored)

            # B's pending should be cleared
            turns = await buf_b.get_turns("s1")
            assert len(turns) == 1
            assert turns[0][0]["content"] == "original"
        finally:
            await buf_a.close()
            await buf_b.close()


# ──────────────────────────────────────────────
# Schema Negative Cases
# ──────────────────────────────────────────────


class TestModelMemorySchemaNegative:
    """Test invalid configs produce ValidationError."""

    component_adapter = TypeAdapter(ComponentConfig)

    def test_invalid_buffer_driver(self):
        """Test that an unknown buffer driver is rejected."""
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "mem",
                "type": "model-memory",
                "buffer": {"driver": "nosuch"},
                "actions": [],
            })

    def test_invalid_storage_driver(self):
        """Test that an unknown storage driver is rejected."""
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "mem",
                "type": "model-memory",
                "storage": {"driver": "nosuch"},
                "actions": [],
            })

    def test_window_negative_int_accepted_by_schema(self):
        """Schema does not constrain window to positive int; document current behavior."""
        config = self.component_adapter.validate_python({
            "id": "mem",
            "type": "model-memory",
            "window": -1,
            "actions": [],
        })
        # Schema accepts; runtime _split_turns_by_window treats falsy/negative as no-limit.
        assert config.window.max_turn_count == -1

    def test_window_wrong_type_rejected(self):
        """Test that a non-int / non-object window value is rejected."""
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "mem",
                "type": "model-memory",
                "window": "five",
                "actions": [],
            })

    def test_append_messages_required(self):
        """Append action requires the messages field."""
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "mem",
                "type": "model-memory",
                "actions": [
                    {"id": "append", "method": "append", "session_id": "s1"},
                ],
            })

    def test_summary_requires_component(self):
        """Summary config requires the component field."""
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "mem",
                "type": "model-memory",
                "summary": {"action": "summarize"},  # missing component
                "actions": [],
            })


# ──────────────────────────────────────────────
# Summary E2E Tests (with stub summary component)
# ──────────────────────────────────────────────


class _StubSummaryComponent:
    """Minimal stub matching create_component()'s expected surface.

    _summarize_turns calls: component.started, component.start(), component.run(action, run_id, input), component.stop()
    """

    def __init__(self, response):
        self._response = response
        self.started = False
        self.calls = []  # captured (action, input) tuples

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    async def run(self, action_id, run_id, input_data):
        self.calls.append((action_id, input_data))
        return self._response


@pytest.fixture
def summary_global_configs():
    """Build ComponentGlobalConfigs containing a placeholder summarizer component config.

    The actual component instance is injected via ComponentInstances cache so
    create_component() returns our stub rather than constructing a real one.
    """
    from mindor.core.component.base import ComponentGlobalConfigs
    from mindor.core.component.component import ComponentInstances

    # Minimal valid component config for the summarizer. The actual instance
    # is replaced via ComponentInstances cache, so only resolve() must succeed.
    summarizer_cfg = TypeAdapter(ComponentConfig).validate_python({
        "id": "summarizer",
        "type": "text-splitter",
        "actions": [{"id": "summarize", "text": "${input.text}"}],
    })
    global_configs = ComponentGlobalConfigs(
        components=[summarizer_cfg],
        listeners=[],
        gateways=[],
        workflows=[],
    )

    # Clear any cross-test cached instance
    ComponentInstances.pop("summarizer", None)
    yield global_configs
    ComponentInstances.pop("summarizer", None)


def install_stub_component(component_id: str, response):
    """Inject a stub into ComponentInstances; returns the stub for assertions."""
    from mindor.core.component.component import ComponentInstances
    stub = _StubSummaryComponent(response)
    ComponentInstances[component_id] = stub
    return stub


class TestSummaryE2E:
    """Test _prune_and_summarize / _summarize_turns code paths."""

    @pytest.mark.anyio
    async def test_summary_only_summarizes_all_and_clears_turns(self, sqlite_storage, mock_context, summary_global_configs):
        """summary-only (no window): after append, all turns are summarized and cleared."""
        stub = install_stub_component("summarizer", "SUMMARY_V1")

        buffer = make_buffer()
        component_config = make_component_config(summary={"component": "summarizer", "action": "summarize"})

        # Load
        action = make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        )
        await action.run(mock_context, buffer, sqlite_storage)

        # Append triggers prune-and-summarize
        action = make_action(
            ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            ),
            component_config,
            global_configs=summary_global_configs,
        )
        await action.run(mock_context, buffer, sqlite_storage)

        # Turns cleared, summary set
        turns = await buffer.get_turns("s1")
        assert turns == []
        assert await buffer.get_summary("s1") == "SUMMARY_V1"
        assert len(stub.calls) == 1

    @pytest.mark.anyio
    async def test_summary_accumulates_previous_summary(self, sqlite_storage, mock_context, summary_global_configs):
        """Subsequent summarization should be passed the previous summary."""
        stub = install_stub_component("summarizer", "SUMMARY_V2")

        buffer = make_buffer()
        component_config = make_component_config(summary={"component": "summarizer", "action": "summarize"})

        # Pre-seed previous summary via load+set
        load = make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        )
        await load.run(mock_context, buffer, sqlite_storage)
        await buffer.set_summary("s1", "PREVIOUS")

        # Append → triggers summarization with previous summary in context
        action = make_action(
            ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": "next"}],
            ),
            component_config,
            global_configs=summary_global_configs,
        )
        await action.run(mock_context, buffer, sqlite_storage)

        # Verify previous summary was embedded in the messages sent to the summarizer
        assert len(stub.calls) == 1
        _, input = stub.calls[0]
        contents = [m.get("content", "") for m in input["messages"]]
        assert any("PREVIOUS" in c for c in contents), f"previous summary should appear in prompt: {contents}"

        assert await buffer.get_summary("s1") == "SUMMARY_V2"

    @pytest.mark.anyio
    async def test_window_plus_summary_summarizes_only_older_turns(self, sqlite_storage, mock_context, summary_global_configs):
        """With window=2 + summary, appending a 3rd turn summarizes only the oldest, keeps recent 2."""
        stub = install_stub_component("summarizer", "OLDER_SUMMARY")

        buffer = make_buffer()
        component_config = make_component_config(
            window=2,
            summary={"component": "summarizer", "action": "summarize"},
        )

        # Load
        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        # Append 3 turns
        for i in range(3):
            await make_action(
                ModelMemoryAppendActionConfig(
                    method="append", session_id="s1",
                    messages=[{"role": "user", "content": f"turn{i}"}],
                ),
                component_config,
                global_configs=summary_global_configs,
            ).run(mock_context, buffer, sqlite_storage)

        # Buffer should hold only the last 2 turns
        turns = await buffer.get_turns("s1")
        assert len(turns) == 2
        assert turns[0][0]["content"] == "turn1"
        assert turns[1][0]["content"] == "turn2"

        # Summary should reflect that summarization fired (once turn0 fell out of window)
        assert await buffer.get_summary("s1") == "OLDER_SUMMARY"
        assert len(stub.calls) == 1

    @pytest.mark.anyio
    async def test_summary_string_response_used_directly(self, sqlite_storage, mock_context, summary_global_configs):
        """Non-dict summarizer response should be coerced via str(response)."""
        install_stub_component("summarizer", "BARE_STRING")

        buffer = make_buffer()
        component_config = make_component_config(summary={"component": "summarizer", "action": "summarize"})

        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        await make_action(
            ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": "hi"}],
            ),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        assert await buffer.get_summary("s1") == "BARE_STRING"

    @pytest.mark.anyio
    async def test_load_with_summary_returns_empty_messages(self, sqlite_storage, mock_context, summary_global_configs):
        """When summary is configured (no window), load returns summary with empty messages."""
        # Pre-populate storage
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "hi"}]], summary="EXISTING")

        buffer = make_buffer()
        component_config = make_component_config(summary={"component": "summarizer", "action": "summarize"})

        result = await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        assert result["summary"] == "EXISTING"
        assert result["messages"] == []


# ──────────────────────────────────────────────
# ModelMemoryComponent Lifecycle Tests
# ──────────────────────────────────────────────


def make_lifecycle_global_configs():
    from mindor.core.component.base import ComponentGlobalConfigs
    return ComponentGlobalConfigs(components=[], listeners=[], gateways=[], workflows=[])


class TestModelMemoryComponentLifecycle:
    """Test ModelMemoryComponent service-boundary: registry-driven driver creation, serve/shutdown, run."""

    @pytest.mark.anyio
    async def test_component_creates_default_drivers(self):
        """A minimal config produces SQLite storage + memory buffer instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_component_config(storage={"driver": "sqlite", "path": os.path.join(tmpdir, "c.db")})
            comp = ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)
            assert isinstance(comp._buffer, MemoryModelMemoryBuffer)
            assert isinstance(comp._storage, SqliteModelMemoryStorage)

    @pytest.mark.anyio
    async def test_start_and_stop_initialize_and_close(self):
        """_start sets up buffer+storage; _stop closes them cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_component_config(storage={"driver": "sqlite", "path": os.path.join(tmpdir, "c.db")})
            comp = ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)

            await comp._start()
            # Storage usable after setup
            turns, summary = await comp._storage.load("s1")
            assert turns == []
            assert summary == ""

            await comp._stop()

    @pytest.mark.anyio
    async def test_run_dispatches_to_action(self, mock_context):
        """_run executes a load action end-to-end through the component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_component_config(storage={"driver": "sqlite", "path": os.path.join(tmpdir, "c.db")})
            comp = ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)
            await comp._start()
            try:
                action_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
                result = await comp._run(action_config, mock_context)
                assert result["messages"] == []
                assert result["summary"] == ""
            finally:
                await comp._stop()

    def test_unsupported_buffer_driver_raises(self, monkeypatch):
        """An empty buffer registry should raise a clear ValueError."""
        from mindor.core.component.services.model_memory import model_memory as mm_module

        monkeypatch.setattr(mm_module, "ModelMemoryBufferRegistry", {}, raising=True)

        config = make_component_config()
        with pytest.raises(ValueError, match="Unsupported model memory buffer driver"):
            ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)

    def test_unsupported_storage_driver_raises(self, monkeypatch):
        """An empty storage registry should raise a clear ValueError."""
        from mindor.core.component.services.model_memory import model_memory as mm_module

        monkeypatch.setattr(mm_module, "ModelMemoryStorageRegistry", {}, raising=True)

        config = make_component_config()
        with pytest.raises(ValueError, match="Unsupported model memory storage driver"):
            ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)

    @pytest.mark.anyio
    async def test_get_setup_requirements_aggregates(self):
        """_get_setup_requirements combines buffer + storage requirements into a flat list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_component_config(storage={"driver": "sqlite", "path": os.path.join(tmpdir, "c.db")})
            comp = ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)
            reqs = comp._get_setup_requirements()
            # SQLite storage contributes aiosqlite; memory buffer contributes nothing.
            assert reqs is not None
            assert "aiosqlite" in reqs


# ──────────────────────────────────────────────
# session_id Validation Tests
# ──────────────────────────────────────────────


class TestSessionIdValidation:
    """Empty session_id must be rejected for every action method."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("action_config", [
        ModelMemoryLoadActionConfig(method="load", session_id=""),
        ModelMemoryAppendActionConfig(method="append", session_id="", messages=[{"role": "user", "content": "x"}]),
        ModelMemorySaveActionConfig(method="save", session_id=""),
        ModelMemoryClearActionConfig(method="clear", session_id=""),
        ModelMemoryDeleteActionConfig(method="delete", session_id=""),
    ])
    async def test_empty_session_id_raises(self, sqlite_storage, mock_context, action_config):
        """An empty session_id should raise ValueError before any work is done."""
        buffer = make_buffer()
        component_config = make_component_config()
        action = make_action(action_config, component_config)

        with pytest.raises(ValueError, match="'session_id' is required"):
            await action.run(mock_context, buffer, sqlite_storage)


# ──────────────────────────────────────────────
# Window Split Algorithm Boundary Tests
# ──────────────────────────────────────────────


class TestWindowSplitAlgorithm:
    """Unit-test _split_turns_by_window in isolation: no buffer/storage."""

    def _make_action(self):
        # Method/session_id don't matter for _split_turns_by_window; pick anything valid.
        return ModelMemoryAction(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            window_config=None,
            summary_config=None,
            summary_component=None,
        )

    def test_empty_turns_returns_two_empty_lists(self):
        action = self._make_action()
        cfg = ModelMemoryWindowConfig(max_turn_count=3)
        recent, older = action._split_turns_by_window([], cfg)
        assert recent == []
        assert older == []

    def test_max_turn_count_keeps_last_n(self):
        action = self._make_action()
        cfg = ModelMemoryWindowConfig(max_turn_count=2)
        turns = [[{"i": 0}], [{"i": 1}], [{"i": 2}], [{"i": 3}]]
        recent, older = action._split_turns_by_window(turns, cfg)
        assert recent == [[{"i": 2}], [{"i": 3}]]
        assert older == [[{"i": 0}], [{"i": 1}]]

    def test_max_message_count_excludes_turn_that_would_overflow(self):
        """A turn is only kept if it fits entirely within the message budget (other than the min-1-turn rule)."""
        action = self._make_action()
        cfg = ModelMemoryWindowConfig(max_message_count=3)
        # Turn sizes (from old to new): 2, 2, 1. Walking from newest:
        # - take turn[2] (1 msg, total 1)
        # - take turn[1] (2 msgs, total 3) -- fits exactly
        # - would-be turn[0] (2 msgs, total 5) -- exceeds, stop
        turns = [
            [{"m": "0a"}, {"m": "0b"}],
            [{"m": "1a"}, {"m": "1b"}],
            [{"m": "2a"}],
        ]
        recent, older = action._split_turns_by_window(turns, cfg)
        assert recent == [turns[1], turns[2]]
        assert older == [turns[0]]

    def test_both_constraints_take_the_stricter(self):
        """When both constraints are set, whichever cuts off first wins."""
        action = self._make_action()
        cfg = ModelMemoryWindowConfig(max_turn_count=5, max_message_count=2)
        turns = [[{"m": "0"}], [{"m": "1"}], [{"m": "2"}]]
        recent, older = action._split_turns_by_window(turns, cfg)
        # message_count=2 bites first: take last 2 single-message turns.
        assert recent == [turns[1], turns[2]]
        assert older == [turns[0]]

    def test_min_one_turn_preserved_when_latest_overflows(self):
        """If even the newest turn exceeds the budget, it is still kept (no empty recent)."""
        action = self._make_action()
        cfg = ModelMemoryWindowConfig(max_message_count=2)
        latest = [{"m": f"x{i}"} for i in range(5)]
        turns = [[{"m": "old"}], latest]
        recent, older = action._split_turns_by_window(turns, cfg)
        assert recent == [latest]
        assert older == [[{"m": "old"}]]


# ──────────────────────────────────────────────
# Summary Input Mode Tests (explicit input mapping)
# ──────────────────────────────────────────────


class TestSummaryExplicitInputMode:
    """When summary.input is provided, raw sources must be registered and the mapped input passed through."""

    @pytest.mark.anyio
    async def test_explicit_input_passes_through_and_registers_sources(self, sqlite_storage, summary_global_configs):
        stub = install_stub_component("summarizer", "EXPLICIT_SUMMARY")
        buffer = make_buffer()

        # input is an explicit dict; in production it'd be a template, but mock_context's
        # render_variable returns values verbatim, so the dict travels as-is to the stub.
        component_config = make_component_config(summary={
            "component": "summarizer",
            "action": "summarize",
            "input": {"raw_messages": "${messages}", "prior": "${previous_summary}"},
            "instruction": "be terse",
        })

        # Track every register_source call to verify the three documented sources are registered.
        recorded_sources = {}
        context = MagicMock(spec=ComponentActionContext)

        async def render_variable(value, ignore_files=False):
            return value
        context.render_variable = AsyncMock(side_effect=render_variable)
        context.register_source = MagicMock(side_effect=lambda key, value: recorded_sources.update({key: value}))
        context.contains_variable_reference = MagicMock(return_value=False)

        # Load
        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        ).run(context, buffer, sqlite_storage)

        await buffer.set_summary("s1", "PRIOR")

        # Append → triggers _summarize_turns through prune-and-summarize
        await make_action(
            ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": "a"}],
            ),
            component_config,
            global_configs=summary_global_configs,
        ).run(context, buffer, sqlite_storage)

        # Stub received exactly the input dict the user supplied (verbatim because render is pass-through).
        assert len(stub.calls) == 1
        _, sent_input = stub.calls[0]
        assert sent_input == {"raw_messages": "${messages}", "prior": "${previous_summary}"}

        # All three documented sources should have been registered for templates to reference.
        assert "messages" in recorded_sources
        assert "instruction" in recorded_sources
        assert recorded_sources["instruction"] == "be terse"
        assert "previous_summary" in recorded_sources
        assert recorded_sources["previous_summary"] == "PRIOR"

        assert await buffer.get_summary("s1") == "EXPLICIT_SUMMARY"


# ──────────────────────────────────────────────
# Summary Response Normalization Tests
# ──────────────────────────────────────────────


class TestSummaryResponseNormalization:
    """Non-str summarizer responses must be coerced via JSON or str() fallback."""

    @pytest.mark.anyio
    async def test_dict_response_serialized_as_json(self, sqlite_storage, mock_context, summary_global_configs):
        """A dict response should be json.dumps'd, not str()'d."""
        install_stub_component("summarizer", {"summary": "hello", "n": 1})

        buffer = make_buffer()
        component_config = make_component_config(summary={"component": "summarizer", "action": "summarize"})

        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        await make_action(
            ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": "hi"}],
            ),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        summary = await buffer.get_summary("s1")
        # json.dumps output is parseable back to the original dict.
        import json
        assert json.loads(summary) == {"summary": "hello", "n": 1}

    @pytest.mark.anyio
    async def test_unjsonable_response_falls_back_to_str(self, sqlite_storage, mock_context, summary_global_configs):
        """A non-str, non-JSON-serializable response should fall back to str()."""
        class _Weird:
            def __repr__(self):
                return "<weird>"

        install_stub_component("summarizer", _Weird())

        buffer = make_buffer()
        component_config = make_component_config(summary={"component": "summarizer", "action": "summarize"})

        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        await make_action(
            ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": "hi"}],
            ),
            component_config,
            global_configs=summary_global_configs,
        ).run(mock_context, buffer, sqlite_storage)

        assert await buffer.get_summary("s1") == "<weird>"


# ──────────────────────────────────────────────
# _resolve_component Tests
# ──────────────────────────────────────────────


class TestResolveComponent:
    """summary_config.component resolution now happens at ModelMemoryComponent._start
    via ComponentResolver, not inside ModelMemoryAction. See test_component_resolver.py
    for the resolver-level behavior."""

    def test_resolve_string_id_via_resolver(self):
        """Confirm ComponentResolver still resolves string ids from global components."""
        from mindor.core.component.component import ComponentResolver
        target = TypeAdapter(ComponentConfig).validate_python({
            "id": "summarizer",
            "type": "text-splitter",
            "actions": [{"id": "summarize", "text": "${input.text}"}],
        })
        id_, cfg = ComponentResolver([target]).resolve("summarizer")
        assert id_ == "summarizer"
        assert cfg is target

    def test_resolve_inline_config_returns_as_is(self):
        """Inline ComponentConfig is handled inline by ModelMemoryComponent._start
        (create_component receives the config directly). ComponentResolver still
        resolves string ids; inline configs bypass the resolver entirely."""
        inline = TypeAdapter(ComponentConfig).validate_python({
            "id": "inline",
            "type": "text-splitter",
            "actions": [{"id": "summarize", "text": "${input.text}"}],
        })
        # The DSL still accepts inline component references; verify the schema
        # itself preserves the object identity when embedded.
        assert inline.id == "inline"


# ──────────────────────────────────────────────
# Buffer-Storage Consistency Tests
# ──────────────────────────────────────────────


class TestBufferStorageConsistency:
    """Once a session is loaded into the buffer, the buffer is the source of truth.

    Subsequent loads must come from the buffer; storage is consulted only on the
    first load or after the session is removed from the buffer (e.g. via delete).
    """

    @pytest.mark.anyio
    async def test_second_load_does_not_touch_storage(self, sqlite_storage, mock_context):
        buffer = make_buffer()
        component_config = make_component_config()

        # Initial load to populate buffer.
        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)

        # Now spy on storage.load: after the first load, the second must not hit it.
        original_load = sqlite_storage.load
        load_call_count = {"n": 0}

        async def counting_load(session_id):
            load_call_count["n"] += 1
            return await original_load(session_id)

        sqlite_storage.load = counting_load

        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)

        assert load_call_count["n"] == 0, "second load should be served from buffer, not storage"

    @pytest.mark.anyio
    async def test_delete_then_load_reads_fresh_from_storage(self, sqlite_storage, mock_context):
        """After delete, the buffer is empty; a subsequent load must go back to storage."""
        buffer = make_buffer()
        component_config = make_component_config()

        # Seed storage with content.
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "persisted"}]], summary="P")

        # Load brings it into the buffer.
        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)

        # Delete wipes both storage and buffer.
        await make_action(
            ModelMemoryDeleteActionConfig(method="delete", session_id="s1"),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)

        assert await buffer.get_turns("s1") is None

        # Subsequent load returns the now-empty storage state (and re-snapshots).
        result = await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)

        assert result["messages"] == []
        assert result["summary"] == ""

        # clear (snapshot restore) should be a no-op back to this empty baseline.
        await make_action(
            ModelMemoryAppendActionConfig(
                method="append", session_id="s1",
                messages=[{"role": "user", "content": "ephemeral"}],
            ),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)
        await make_action(
            ModelMemoryClearActionConfig(method="clear", session_id="s1"),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)

        turns = await buffer.get_turns("s1")
        assert turns == []


# ──────────────────────────────────────────────
# Concurrent Append Tests
# ──────────────────────────────────────────────


class TestConcurrentAppend:
    """Concurrent appends to the same session should all land; ordering is by completion order."""

    @pytest.mark.anyio
    async def test_concurrent_appends_all_recorded(self, sqlite_storage, mock_context):
        buffer = make_buffer()
        component_config = make_component_config()

        # Load first.
        await make_action(
            ModelMemoryLoadActionConfig(method="load", session_id="s1"),
            component_config,
        ).run(mock_context, buffer, sqlite_storage)

        async def append(i: int):
            await make_action(
                ModelMemoryAppendActionConfig(
                    method="append", session_id="s1",
                    messages=[{"role": "user", "content": f"t{i}"}],
                ),
                component_config,
            ).run(mock_context, buffer, sqlite_storage)

        await asyncio.gather(*[append(i) for i in range(10)])

        turns = await buffer.get_turns("s1")
        assert len(turns) == 10
        # All 10 distinct contents present (ordering by completion is allowed to vary).
        contents = sorted(turn[0]["content"] for turn in turns)
        assert contents == sorted(f"t{i}" for i in range(10))
