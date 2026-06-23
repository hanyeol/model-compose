"""Tests for the WebSocketManager used by the HTTP server controller adapter."""

import inspect
import json
from typing import Annotated, Optional, get_type_hints

import pytest

from pydantic import BaseModel, ValidationError
from unittest.mock import AsyncMock, MagicMock

from mindor.dsl.schema.controller.adapter.impl.http_server import (
    HttpServerControllerAdapterConfig,
    WebSocketConfig,
)
from mindor.dsl.schema.controller.adapter.impl.types import ControllerAdapterType
from mindor.core.controller.adapters.services.http_server import (
    HttpServerControllerAdapterService,
    PingPayload,
    TaskGetPayload,
    TaskResumePayload,
    TaskSubscribePayload,
    TaskUnsubscribePayload,
    WebSocketManager,
    WebSocketMessage,
    WebSocketRouter,
    WorkflowRunPayload,
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


class TestWebSocketRouter:
    def test_handler_registers_and_resolves(self):
        router = WebSocketRouter()

        @router.handler("ping")
        async def ping(client_id, message_id, data):
            return "pong"

        resolved = router.resolve("ping")
        assert resolved is ping

    def test_resolve_unknown_returns_none(self):
        router = WebSocketRouter()
        assert router.resolve("missing") is None

    def test_duplicate_registration_last_wins(self):
        router = WebSocketRouter()

        @router.handler("dup")
        async def first(client_id, message_id, data):
            return "first"

        @router.handler("dup")
        async def second(client_id, message_id, data):
            return "second"

        resolved = router.resolve("dup")
        assert resolved is second

    @pytest.mark.anyio
    async def test_pydantic_payload_is_coerced_when_annotated(self):
        router = WebSocketRouter()

        class Payload(BaseModel):
            name: str
            count: int

        received = {}

        @router.handler("typed")
        async def typed(client_id, message_id, data: Payload):
            received["payload"] = data
            return data

        handler = router.resolve("typed")
        # The decorator should have wrapped the function with a coercing wrapper,
        # so the resolved handler is NOT the original function.
        assert handler is not typed

        await handler("client-1", "msg-1", {"name": "alice", "count": 3})
        assert isinstance(received["payload"], Payload)
        assert received["payload"].name == "alice"
        assert received["payload"].count == 3

    @pytest.mark.anyio
    async def test_handler_without_pydantic_annotation_is_called_raw(self):
        router = WebSocketRouter()
        received = {}

        @router.handler("raw")
        async def raw(client_id, message_id, data):
            received["data"] = data

        handler = router.resolve("raw")
        # No pydantic annotation → no wrapper, original function is stored.
        assert handler is raw

        await handler("client-1", "msg-1", {"foo": "bar"})
        assert received["data"] == {"foo": "bar"}

    @pytest.mark.anyio
    async def test_invalid_payload_raises_validation_error(self):
        router = WebSocketRouter()

        class Payload(BaseModel):
            name: str

        @router.handler("typed")
        async def typed(client_id, message_id, data: Payload):
            pass

        handler = router.resolve("typed")
        with pytest.raises(ValidationError):
            await handler("c1", "m1", {})

    def test_annotated_type_does_not_raise(self):
        """Annotated[...] hints (non-class) fall back to raw dict without TypeError."""
        router = WebSocketRouter()

        @router.handler("annotated")
        async def annotated(client_id, message_id, payload: Annotated[dict, "meta"]):
            pass

        # If issubclass were called without isinstance(t, type) guard, decorator
        # registration above would have raised TypeError.
        assert router.resolve("annotated") is annotated

    def test_wrapper_preserves_function_identity(self):
        """functools.wraps preserves __name__ and __wrapped__."""
        router = WebSocketRouter()

        class Payload(BaseModel):
            name: str

        @router.handler("typed")
        async def typed(client_id, message_id, data: Payload):
            pass

        wrapper = router.resolve("typed")
        assert wrapper is not typed
        assert wrapper.__name__ == "typed"
        assert wrapper.__wrapped__ is typed


class TestAdapterHandlerRegistration:
    """Guards against silent fallback to raw dict in the adapter's typed handlers.

    If get_type_hints() fails silently (e.g. missing import for a payload model),
    the decorator skips wrapping and the handler receives a raw dict instead of
    a validated model. These tests assert each handler is registered as a
    typed wrapper bound to the expected payload model.
    """

    @pytest.fixture
    def adapter(self):
        config = HttpServerControllerAdapterConfig(
            type=ControllerAdapterType.HTTP_SERVER,
            websocket=WebSocketConfig(),
        )
        controller = MagicMock()
        return HttpServerControllerAdapterService(config, controller, daemon=False)

    @pytest.mark.parametrize("message_type,payload_model", [
        ("run_workflow", WorkflowRunPayload),
        ("subscribe_task", TaskSubscribePayload),
        ("unsubscribe_task", TaskUnsubscribePayload),
        ("resume_task", TaskResumePayload),
        ("get_task", TaskGetPayload),
        ("ping", PingPayload),
    ])
    def test_handler_registered_as_typed_wrapper(self, adapter, message_type, payload_model):
        handler = adapter.websocket_router.resolve(message_type)
        assert handler is not None, f"missing handler: {message_type}"

        wrapped = getattr(handler, "__wrapped__", None)
        assert wrapped is not None, (
            f"{message_type} handler is not wrapped — silent fallback to raw dict. "
            "Check that the payload model is importable and the type hint resolves."
        )

        last_param = list(inspect.signature(wrapped).parameters)[-1]
        hints = get_type_hints(wrapped)
        assert hints.get(last_param) is payload_model


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
