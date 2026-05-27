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
    """Create a ModelMemoryAction instance with optional global configs."""
    if global_configs is None:
        global_configs = MagicMock()
    return ModelMemoryAction(action_config, component_config, global_configs)


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
        assert result["total_message_count"] == 0

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
        assert result["success"] is True
        assert result["buffer_turn_count"] == 1

        # Save
        save_config = ModelMemorySaveActionConfig(method="save", session_id="s1")
        action = make_action(save_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)
        assert result["success"] is True
        assert result["turn_count"] == 1

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
        assert result["total_message_count"] == 4
        assert result["window_message_count"] == 4
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

        assert result["total_message_count"] == 5
        assert result["window_message_count"] == 2
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
        assert result["success"] is True

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
        assert result["success"] is True

        # Verify
        assert await buffer.get_turns("s1") is None
        turns, _ = await sqlite_storage.load("s1")
        assert turns == []

    @pytest.mark.anyio
    async def test_save_with_implicit_load(self, sqlite_storage, mock_context):
        """Save without prior load should auto-load from storage."""
        await sqlite_storage.save("s1", turns=[[{"role": "user", "content": "old"}]], summary="")

        buffer = make_buffer()
        component_config = make_component_config()

        # Save with messages (no prior load)
        new_messages = [{"role": "user", "content": "new"}]
        save_config = ModelMemorySaveActionConfig(method="save", session_id="s1", messages=new_messages)
        action = make_action(save_config, component_config)
        result = await action.run(mock_context, buffer, sqlite_storage)
        assert result["success"] is True
        assert result["turn_count"] == 2

        # Verify persisted
        turns, _ = await sqlite_storage.load("s1")
        assert len(turns) == 2

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

        with pytest.raises(ValueError, match="Session not loaded"):
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
        assert result["turn_count"] == 2

        # Simulate fresh start: new buffer, reload from storage
        buffer2 = make_buffer()
        load_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
        action = make_action(load_config, component_config)
        result = await action.run(mock_context, buffer2, sqlite_storage)

        assert result["total_message_count"] == 3
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
        assert result["success"] is True
        assert result["turn_count"] == 1  # one empty turn appended

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

        with pytest.raises(ValueError, match="messages must be a list"):
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
        assert result["window_message_count"] == 10
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

        assert result["total_message_count"] == 1
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
    await buf._pubsub.subscribe(buf._channel)
    buf._listener_task = asyncio.create_task(buf._listen())
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
    await buf._pubsub.subscribe(buf._channel)
    buf._listener_task = asyncio.create_task(buf._listen())
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
        # Schema accepts; runtime _apply_window treats falsy/negative as no-limit.
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

    _invoke_summary calls: component.started, component.start(), component.run(action, run_id, input), component.stop()
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
    """Test _prune_and_summarize / _invoke_summary code paths."""

    @pytest.mark.anyio
    async def test_summary_only_summarizes_all_and_clears_turns(self, sqlite_storage, mock_context, summary_global_configs):
        """summary-only (no window): after append, all turns are summarized and cleared."""
        stub = install_stub_component("summarizer", {"content": "SUMMARY_V1"})

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
        stub = install_stub_component("summarizer", {"content": "SUMMARY_V2"})

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

        # Stub was invoked; verify register_source was called with previous_summary
        mock_calls = [c.args for c in mock_context.register_source.call_args_list]
        prev_sources = [args for args in mock_calls if args and args[0] == "previous_summary"]
        assert prev_sources, "previous_summary should be registered as a source"
        assert prev_sources[-1][1] == "PREVIOUS"

        assert await buffer.get_summary("s1") == "SUMMARY_V2"
        assert len(stub.calls) == 1

    @pytest.mark.anyio
    async def test_window_plus_summary_summarizes_only_older_turns(self, sqlite_storage, mock_context, summary_global_configs):
        """With window=2 + summary, appending a 3rd turn summarizes only the oldest, keeps recent 2."""
        stub = install_stub_component("summarizer", {"content": "OLDER_SUMMARY"})

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
        assert result["total_message_count"] == 1
        assert result["window_message_count"] == 0


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
    async def test_serve_and_shutdown_initialize_and_close(self):
        """_serve sets up buffer+storage; _shutdown closes them cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_component_config(storage={"driver": "sqlite", "path": os.path.join(tmpdir, "c.db")})
            comp = ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)

            await comp._serve()
            # Storage usable after setup
            turns, summary = await comp._storage.load("s1")
            assert turns == []
            assert summary == ""

            await comp._shutdown()

    @pytest.mark.anyio
    async def test_run_dispatches_to_action(self, mock_context):
        """_run executes a load action end-to-end through the component."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_component_config(storage={"driver": "sqlite", "path": os.path.join(tmpdir, "c.db")})
            comp = ModelMemoryComponent("mem", config, make_lifecycle_global_configs(), daemon=False)
            await comp._serve()
            try:
                action_config = ModelMemoryLoadActionConfig(method="load", session_id="s1")
                result = await comp._run(action_config, mock_context)
                assert result["messages"] == []
                assert result["summary"] == ""
                assert result["total_message_count"] == 0
            finally:
                await comp._shutdown()

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
