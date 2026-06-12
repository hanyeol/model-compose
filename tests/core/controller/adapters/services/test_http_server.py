"""Tests for the WebSocketManager used by the HTTP server controller adapter."""

import json

import pytest

from unittest.mock import AsyncMock

from mindor.core.controller.adapters.services.http_server import (
    WebSocketManager,
    WebSocketMessage,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_websocket():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestWebSocketManagerAccept:
    @pytest.mark.anyio
    async def test_accept_registers_connection(self):
        manager = WebSocketManager()
        ws = make_websocket()
        result = await manager.accept("client-1", ws)
        assert result is True
        ws.accept.assert_awaited_once()
        assert manager.has_connection("client-1")

    @pytest.mark.anyio
    async def test_accept_duplicate_session_rejects(self):
        manager = WebSocketManager()
        ws1 = make_websocket()
        ws2 = make_websocket()
        await manager.accept("client-1", ws1)
        result = await manager.accept("client-1", ws2)
        assert result is False
        ws2.close.assert_awaited_once_with(code=4409, reason="Session already connected")

    @pytest.mark.anyio
    async def test_has_connection_false_before_accept(self):
        manager = WebSocketManager()
        assert manager.has_connection("unknown") is False


class TestWebSocketManagerClose:
    @pytest.mark.anyio
    async def test_close_removes_connection(self):
        manager = WebSocketManager()
        ws = make_websocket()
        await manager.accept("client-1", ws)
        await manager.close("client-1")
        assert not manager.has_connection("client-1")

    @pytest.mark.anyio
    async def test_close_cleans_up_task_subscriptions(self):
        manager = WebSocketManager()
        ws = make_websocket()
        await manager.accept("client-1", ws)
        manager.subscribe_task("client-1", "task-1")
        manager.subscribe_task("client-1", "task-2")
        await manager.close("client-1")
        assert not manager.has_task_subscribers("task-1")
        assert not manager.has_task_subscribers("task-2")

    @pytest.mark.anyio
    async def test_close_nonexistent_is_noop(self):
        manager = WebSocketManager()
        await manager.close("no-such-client")


class TestWebSocketManagerSendMessage:
    @pytest.mark.anyio
    async def test_send_message_delivers_serialized_payload(self):
        manager = WebSocketManager()
        ws = make_websocket()
        await manager.accept("client-1", ws)
        await manager.send_message("client-1", WebSocketMessage(type="ping"))
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "ping"

    @pytest.mark.anyio
    async def test_send_message_unknown_client_is_noop(self):
        manager = WebSocketManager()
        await manager.send_message("nobody", WebSocketMessage(type="ping"))

    @pytest.mark.anyio
    async def test_send_error_emits_error_message(self):
        manager = WebSocketManager()
        ws = make_websocket()
        await manager.accept("client-1", ws)
        await manager.send_error("client-1", "INVALID_REQUEST", "bad input", message_id="msg-1")
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "error"
        assert sent["id"] == "msg-1"
        assert sent["data"] == {"code": "INVALID_REQUEST", "message": "bad input"}


class TestWebSocketManagerSubscriptions:
    @pytest.mark.anyio
    async def test_subscribe_task_records_subscription(self):
        manager = WebSocketManager()
        ws = make_websocket()
        await manager.accept("client-1", ws)
        manager.subscribe_task("client-1", "task-1")
        assert manager.has_task_subscribers("task-1")

    @pytest.mark.anyio
    async def test_unsubscribe_task_removes_subscription(self):
        manager = WebSocketManager()
        ws = make_websocket()
        await manager.accept("client-1", ws)
        manager.subscribe_task("client-1", "task-1")
        manager.unsubscribe_task("client-1", "task-1")
        assert not manager.has_task_subscribers("task-1")

    @pytest.mark.anyio
    async def test_unsubscribe_last_subscriber_clears_entry(self):
        manager = WebSocketManager()
        ws = make_websocket()
        await manager.accept("client-1", ws)
        manager.subscribe_task("client-1", "task-1")
        manager.unsubscribe_task("client-1", "task-1")
        assert not manager.has_task_subscribers("task-1")

    @pytest.mark.anyio
    async def test_broadcast_task_message_reaches_all_subscribers(self):
        manager = WebSocketManager()
        ws1 = make_websocket()
        ws2 = make_websocket()
        await manager.accept("c1", ws1)
        await manager.accept("c2", ws2)
        manager.subscribe_task("c1", "task-1")
        manager.subscribe_task("c2", "task-1")
        await manager.broadcast_task_message("task-1", WebSocketMessage(type="task_state"))
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.anyio
    async def test_broadcast_no_subscribers_is_noop(self):
        manager = WebSocketManager()
        await manager.broadcast_task_message("task-1", WebSocketMessage(type="task_state"))

    @pytest.mark.anyio
    async def test_broadcast_swallows_per_client_errors(self):
        manager = WebSocketManager()
        ws_good = make_websocket()
        ws_bad = make_websocket()
        ws_bad.send_text.side_effect = RuntimeError("broken")
        await manager.accept("good", ws_good)
        await manager.accept("bad", ws_bad)
        manager.subscribe_task("good", "task-1")
        manager.subscribe_task("bad", "task-1")
        await manager.broadcast_task_message("task-1", WebSocketMessage(type="task_state"))
        ws_good.send_text.assert_awaited_once()


class TestWebSocketManagerDispose:
    @pytest.mark.anyio
    async def test_dispose_closes_and_clears_all(self):
        manager = WebSocketManager()
        ws1 = make_websocket()
        ws2 = make_websocket()
        await manager.accept("c1", ws1)
        await manager.accept("c2", ws2)
        manager.subscribe_task("c1", "task-1")
        await manager.dispose()
        ws1.close.assert_awaited_once()
        ws2.close.assert_awaited_once()
        assert not manager.has_connection("c1")
        assert not manager.has_connection("c2")
        assert not manager.has_task_subscribers("task-1")
