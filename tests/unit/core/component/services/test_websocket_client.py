"""Tests for WebSocketClientAction, covering message sending, frame receiving (single,
collect, stream), connection lifecycle, and output rendering."""

import asyncio
import json

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from mindor.core.component.services.websocket_client import WebSocketClientAction, WebSocketClientComponent
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.core.utils.websocket_client import WebSocketClient, WebSocketConnection
from mindor.dsl.schema.action.impl.websocket_client import WebSocketClientActionConfig
from mindor.dsl.schema.action.impl.websocket_server import (
    WebSocketReceiveConfig,
    WebSocketReceiveFormat,
)


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


# ---- Helpers ----

def make_connection(connected=True, frames=None):
    """Create a mock WebSocketConnection."""
    conn = AsyncMock(spec=WebSocketConnection)
    conn.is_connected.return_value = connected
    conn.close = AsyncMock()
    conn.send_message = AsyncMock()
    conn.send_bytes = AsyncMock()
    conn.websocket = MagicMock()
    conn.websocket.send = AsyncMock()

    if frames is not None:
        async def _receive_frames():
            for f in frames:
                yield f
        conn.receive_frames = _receive_frames

    return conn


def make_client(connection=None, params=None):
    """Create a WebSocketClient with a mocked _connect that returns a given connection."""
    client = WebSocketClient(base_url="ws://test", params=params)
    conn = connection or make_connection()
    client._connect = AsyncMock(return_value=conn)
    return client


def make_context(input_data=None, output=None):
    """Create a mock ComponentActionContext."""
    ctx = AsyncMock()
    ctx.render_variable = AsyncMock(side_effect=lambda v, **kw: v)
    ctx.contains_variable_reference = MagicMock(return_value=False)
    ctx.register_source = MagicMock()
    return ctx


def make_action_config(
    path=None,
    params=None,
    headers=None,
    message=None,
    receive_format=WebSocketReceiveFormat.JSON,
    collect=False,
    timeout=None,
    output=None,
):
    """Create a WebSocketClientActionConfig."""
    return WebSocketClientActionConfig(
        path=path,
        params=params or {},
        headers=headers or {},
        message=message,
        receive=WebSocketReceiveConfig(format=receive_format, collect=collect, timeout=timeout),
        output=output,
    )


# ---- WebSocketClientAction Send Tests ----

class TestWebSocketClientActionSend:
    """Tests for WebSocketClientAction message sending behavior."""

    @pytest.mark.anyio
    async def test_send_dict_uses_send_message(self):
        """Dict message is sent via send_message (JSON)."""
        conn = make_connection(frames=[])
        action = WebSocketClientAction(make_action_config(message={"type": "hello"}))

        ctx = make_context()
        client = make_client(conn)

        await action.run(ctx, client)

        conn.send_message.assert_awaited_once_with({"type": "hello"})

    @pytest.mark.anyio
    async def test_send_list_uses_send_message(self):
        """List message is sent via send_message (JSON)."""
        conn = make_connection(frames=[])
        action = WebSocketClientAction(make_action_config(message=[1, 2, 3]))

        ctx = make_context()
        client = make_client(conn)

        await action.run(ctx, client)

        conn.send_message.assert_awaited_once_with([1, 2, 3])

    @pytest.mark.anyio
    async def test_send_bytes_uses_send_bytes(self):
        """Bytes message is sent via send_bytes."""
        conn = make_connection(frames=[])
        action = WebSocketClientAction(make_action_config(message=b"\x00\x01"))

        ctx = make_context()
        client = make_client(conn)

        await action.run(ctx, client)

        conn.send_bytes.assert_awaited_once_with(b"\x00\x01")

    @pytest.mark.anyio
    async def test_send_string_uses_websocket_send(self):
        """String message is sent via websocket.send."""
        conn = make_connection(frames=[])
        action = WebSocketClientAction(make_action_config(message="hello"))

        ctx = make_context()
        client = make_client(conn)

        await action.run(ctx, client)

        conn.websocket.send.assert_awaited_once_with("hello")

    @pytest.mark.anyio
    async def test_no_send_when_message_is_none(self):
        """No send occurs when message is None."""
        conn = make_connection(frames=[])
        action = WebSocketClientAction(make_action_config(message=None))

        ctx = make_context()
        client = make_client(conn)

        await action.run(ctx, client)

        conn.send_message.assert_not_awaited()
        conn.send_bytes.assert_not_awaited()
        conn.websocket.send.assert_not_awaited()


# ---- Receive Tests ----

class TestWebSocketClientActionReceiveSingle:
    """Tests for receiving a single frame from the WebSocket client."""

    @pytest.mark.anyio
    async def test_receive_json_single(self):
        """Single JSON frame is parsed and returned."""
        conn = make_connection(frames=['{"key": "value"}'])
        action = WebSocketClientAction(make_action_config(receive_format=WebSocketReceiveFormat.JSON))

        ctx = make_context()
        client = make_client(conn)

        result = await action.run(ctx, client)

        assert result == {"key": "value"}

    @pytest.mark.anyio
    async def test_receive_text_single(self):
        """Single text frame is returned as-is."""
        conn = make_connection(frames=["hello world"])
        action = WebSocketClientAction(make_action_config(receive_format=WebSocketReceiveFormat.TEXT))

        ctx = make_context()
        client = make_client(conn)

        result = await action.run(ctx, client)

        assert result == "hello world"

    @pytest.mark.anyio
    async def test_receive_binary_single(self):
        """Single binary frame is wrapped in BytesStreamResource."""
        conn = make_connection(frames=[b"\x89PNG"])
        action = WebSocketClientAction(make_action_config(receive_format=WebSocketReceiveFormat.BINARY))

        ctx = make_context()
        client = make_client(conn)

        result = await action.run(ctx, client)

        assert isinstance(result, BytesStreamResource)
        assert result.data == b"\x89PNG"

    @pytest.mark.anyio
    async def test_receive_returns_none_on_empty(self):
        """Returns None when no frames are received."""
        conn = make_connection(frames=[])
        action = WebSocketClientAction(make_action_config(receive_format=WebSocketReceiveFormat.JSON))

        ctx = make_context()
        client = make_client(conn)

        result = await action.run(ctx, client)

        assert result is None


class TestWebSocketClientActionReceiveCollect:
    """Tests for collect mode, which gathers all frames into a single result."""

    @pytest.mark.anyio
    async def test_collect_json(self):
        """Collect mode gathers all JSON frames into a list."""
        conn = make_connection(frames=['{"a":1}', '{"b":2}'])
        action = WebSocketClientAction(make_action_config(
            receive_format=WebSocketReceiveFormat.JSON, collect=True
        ))

        ctx = make_context()
        client = make_client(conn)

        result = await action.run(ctx, client)

        assert result == [{"a": 1}, {"b": 2}]

    @pytest.mark.anyio
    async def test_collect_binary(self):
        """Collect mode concatenates all binary frames."""
        conn = make_connection(frames=[b"\x00\x01", b"\x02\x03"])
        action = WebSocketClientAction(make_action_config(
            receive_format=WebSocketReceiveFormat.BINARY, collect=True
        ))

        ctx = make_context()
        client = make_client(conn)

        result = await action.run(ctx, client)

        assert isinstance(result, BytesStreamResource)
        assert result.data == b"\x00\x01\x02\x03"


# ---- Stream Tests ----

class TestWebSocketClientActionReceiveStream:
    """Tests for streaming mode, which yields frames as an async generator."""

    @pytest.mark.anyio
    async def test_stream_json(self):
        """Streaming mode yields each decoded JSON frame."""
        conn = make_connection(frames=['{"n":1}', '{"n":2}'])
        action = WebSocketClientAction(make_action_config(
            receive_format=WebSocketReceiveFormat.JSON, output="${response[]}"
        ))

        ctx = make_context()
        ctx.contains_variable_reference = MagicMock(return_value=True)
        ctx.render_variable = AsyncMock(side_effect=lambda v, **kw: v)
        client = make_client(conn)

        stream = await action.run(ctx, client)
        items = [item async for item in stream]

        assert len(items) == 2
        assert ctx.register_source.call_count == 2


# ---- Connection Lifecycle Tests ----

class TestWebSocketClientActionConnectionLifecycle:
    """Tests for connection ownership and cleanup after action execution."""

    @pytest.mark.anyio
    async def test_default_connection_not_closed_after_run(self):
        """Default (non-owned) connection is not closed after action completes."""
        conn = make_connection(frames=['{"ok":true}'])
        client = make_client(conn)

        action = WebSocketClientAction(make_action_config())
        ctx = make_context()

        await action.run(ctx, client)

        conn.close.assert_not_awaited()

    @pytest.mark.anyio
    async def test_owned_connection_closed_after_run(self):
        """Owned connection is closed after action completes."""
        conn = make_connection(frames=['{"ok":true}'])
        client = make_client(conn)

        action = WebSocketClientAction(make_action_config(path="/custom"))
        ctx = make_context()

        await action.run(ctx, client)

        conn.close.assert_awaited_once()

    @pytest.mark.anyio
    async def test_owned_connection_closed_on_error(self):
        """Owned connection is closed when an exception occurs."""
        conn = make_connection()
        conn.send_message = AsyncMock(side_effect=RuntimeError("send failed"))
        client = make_client(conn)

        action = WebSocketClientAction(make_action_config(path="/custom", message={"fail": True}))
        ctx = make_context()

        with pytest.raises(RuntimeError, match="send failed"):
            await action.run(ctx, client)

        conn.close.assert_awaited_once()


# ---- Output Tests ----

class TestWebSocketClientActionOutput:
    """Tests for output template rendering after receiving a response."""

    @pytest.mark.anyio
    async def test_output_template_rendered(self):
        """When output is set, render_variable is called with the output template."""
        conn = make_connection(frames=['{"data": "test"}'])
        action = WebSocketClientAction(make_action_config(output="${response.data}"))

        ctx = make_context()
        ctx.render_variable = AsyncMock(side_effect=lambda v, **kw: v)
        client = make_client(conn)

        await action.run(ctx, client)

        ctx.register_source.assert_called_once_with("response", {"data": "test"})

    @pytest.mark.anyio
    async def test_no_output_returns_raw_response(self):
        """When output is None, the raw response is returned."""
        conn = make_connection(frames=['{"raw": true}'])
        action = WebSocketClientAction(make_action_config(output=None))

        ctx = make_context()
        client = make_client(conn)

        result = await action.run(ctx, client)

        assert result == {"raw": True}
