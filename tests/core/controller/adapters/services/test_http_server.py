import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from mindor.core.controller.adapters.services.http_server import (
    WebSocketConnectionManager,
    HttpServerControllerAdapterService,
)
from mindor.core.controller.base import TaskState, TaskStatus, InterruptState
from mindor.dsl.schema.controller.adapter.impl.http_server import (
    HttpServerControllerAdapterConfig,
    WebSocketConfig,
)
from mindor.dsl.schema.controller.adapter.impl.types import ControllerAdapterType


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

def make_websocket():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


def make_task_state(
    task_id="task-1",
    status=TaskStatus.PENDING,
    output=None,
    error=None,
    interrupt=None,
):
    return TaskState(
        task_id=task_id,
        status=status,
        workflow_id="test_workflow",
        output=output,
        error=error,
        interrupt=interrupt,
    )


def make_controller(workflow_ids=None, task_state=None):
    controller = MagicMock()
    ids = workflow_ids or ["__default__"]
    controller.workflow_schemas = {wid: MagicMock(workflow_id=wid) for wid in ids}
    controller.get_task_state = MagicMock(return_value=task_state)
    controller.run_workflow = AsyncMock(return_value=task_state or make_task_state())
    controller.resume_workflow = AsyncMock(return_value=task_state or make_task_state())
    controller.add_task_state_listener = MagicMock()
    controller.remove_task_state_listener = MagicMock()
    return controller


def make_adapter(websocket=True, max_connections=None, controller=None):
    ws_config = WebSocketConfig(max_connections=max_connections) if websocket else False
    config = HttpServerControllerAdapterConfig(
        type=ControllerAdapterType.HTTP_SERVER,
        host="localhost",
        port=8080,
        websocket=ws_config if isinstance(ws_config, WebSocketConfig) else websocket,
    )
    ctrl = controller or make_controller()
    return HttpServerControllerAdapterService(config, ctrl, daemon=False)


# ============================
# WebSocketConnectionManager
# ============================

class TestWebSocketConnectionManagerConnect:
    @pytest.mark.anyio
    async def test_connect_accepts_and_registers(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        result = await manager.connect("client-1", ws)
        assert result is True
        ws.accept.assert_awaited_once()
        assert manager.has_connection("client-1")

    @pytest.mark.anyio
    async def test_connect_duplicate_session_rejects(self):
        manager = WebSocketConnectionManager()
        ws1 = make_websocket()
        ws2 = make_websocket()
        await manager.connect("client-1", ws1)
        result = await manager.connect("client-1", ws2)
        assert result is False
        ws2.close.assert_awaited_once_with(code=4409, reason="Session already connected")

    @pytest.mark.anyio
    async def test_has_connection_false_before_connect(self):
        manager = WebSocketConnectionManager()
        assert manager.has_connection("unknown") is False


class TestWebSocketConnectionManagerDisconnect:
    @pytest.mark.anyio
    async def test_disconnect_removes_connection(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        await manager.connect("client-1", ws)
        await manager.disconnect("client-1")
        assert not manager.has_connection("client-1")

    @pytest.mark.anyio
    async def test_disconnect_cleans_up_task_subscriptions(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        await manager.connect("client-1", ws)
        manager.subscribe_to_task("client-1", "task-1")
        manager.subscribe_to_task("client-1", "task-2")
        await manager.disconnect("client-1")
        assert "client-1" not in (manager._task_subscriptions.get("task-1") or set())
        assert "client-1" not in (manager._task_subscriptions.get("task-2") or set())

    @pytest.mark.anyio
    async def test_disconnect_nonexistent_is_noop(self):
        manager = WebSocketConnectionManager()
        await manager.disconnect("no-such-client")  # should not raise


class TestWebSocketConnectionManagerSendMessage:
    @pytest.mark.anyio
    async def test_send_message_returns_true_on_success(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        await manager.connect("client-1", ws)
        result = await manager.send_message("client-1", {"type": "ping"})
        assert result is True
        ws.send_json.assert_awaited_once_with({"type": "ping"})

    @pytest.mark.anyio
    async def test_send_message_returns_false_for_unknown_client(self):
        manager = WebSocketConnectionManager()
        result = await manager.send_message("nobody", {"type": "ping"})
        assert result is False

    @pytest.mark.anyio
    async def test_send_message_disconnects_on_error(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        ws.send_json.side_effect = RuntimeError("broken pipe")
        await manager.connect("client-1", ws)
        result = await manager.send_message("client-1", {"type": "ping"})
        assert result is False
        assert not manager.has_connection("client-1")


class TestWebSocketConnectionManagerSubscriptions:
    @pytest.mark.anyio
    async def test_subscribe_to_task(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        await manager.connect("client-1", ws)
        manager.subscribe_to_task("client-1", "task-1")
        assert "client-1" in manager._task_subscriptions["task-1"]
        assert "task-1" in manager._client_subscriptions["client-1"]

    @pytest.mark.anyio
    async def test_unsubscribe_from_task(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        await manager.connect("client-1", ws)
        manager.subscribe_to_task("client-1", "task-1")
        manager.unsubscribe_from_task("client-1", "task-1")
        assert "task-1" not in manager._task_subscriptions
        assert "task-1" not in manager._client_subscriptions["client-1"]

    @pytest.mark.anyio
    async def test_unsubscribe_last_subscriber_removes_task_entry(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        await manager.connect("client-1", ws)
        manager.subscribe_to_task("client-1", "task-1")
        manager.unsubscribe_from_task("client-1", "task-1")
        assert "task-1" not in manager._task_subscriptions

    @pytest.mark.anyio
    async def test_broadcast_to_task_subscribers(self):
        manager = WebSocketConnectionManager()
        ws1 = make_websocket()
        ws2 = make_websocket()
        await manager.connect("c1", ws1)
        await manager.connect("c2", ws2)
        manager.subscribe_to_task("c1", "task-1")
        manager.subscribe_to_task("c2", "task-1")
        await manager.broadcast_to_task_subscribers("task-1", {"type": "task_state"})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.anyio
    async def test_broadcast_to_no_subscribers_is_noop(self):
        manager = WebSocketConnectionManager()
        await manager.broadcast_to_task_subscribers("task-1", {"type": "task_state"})

    @pytest.mark.anyio
    async def test_broadcast_disconnects_broken_client(self):
        manager = WebSocketConnectionManager()
        ws = make_websocket()
        ws.send_text.side_effect = RuntimeError("broken")
        await manager.connect("client-1", ws)
        manager.subscribe_to_task("client-1", "task-1")
        await manager.broadcast_to_task_subscribers("task-1", {"type": "task_state"})
        assert not manager.has_connection("client-1")


class TestWebSocketConnectionManagerDisconnectAll:
    @pytest.mark.anyio
    async def test_disconnect_all_clears_everything(self):
        manager = WebSocketConnectionManager()
        ws1 = make_websocket()
        ws2 = make_websocket()
        await manager.connect("c1", ws1)
        await manager.connect("c2", ws2)
        manager.subscribe_to_task("c1", "task-1")
        await manager.disconnect_all()
        assert not manager.has_connection("c1")
        assert not manager.has_connection("c2")


# ============================
# HttpServerControllerAdapterService
# ============================

class TestHttpServerAdapterInit:
    def test_websocket_manager_created(self):
        adapter = make_adapter()
        assert isinstance(adapter.websocket_manager, WebSocketConnectionManager)

    def test_websocket_disabled_skips_route(self):
        adapter = make_adapter(websocket=False)
        # WebSocket route not registered — no exception during creation
        assert adapter is not None


class TestHttpServerAdapterStartShutdown:
    @pytest.mark.anyio
    async def test_start_registers_listener(self):
        controller = make_controller()
        adapter = make_adapter(controller=controller)
        await adapter._start()
        controller.add_task_state_listener.assert_called_once_with(adapter._on_task_state_change)

    @pytest.mark.anyio
    async def test_shutdown_removes_listener(self):
        controller = make_controller()
        adapter = make_adapter(controller=controller)
        await adapter._start()
        await adapter._shutdown()
        controller.remove_task_state_listener.assert_called_once_with(adapter._on_task_state_change)

    @pytest.mark.anyio
    async def test_shutdown_disconnects_all_clients(self):
        controller = make_controller()
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)
        await adapter._shutdown()
        assert not adapter.websocket_manager.has_connection("client-1")


class TestOnTaskStateChange:
    @pytest.mark.anyio
    async def test_broadcasts_task_state_to_subscribers(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)
        adapter.websocket_manager.subscribe_to_task("client-1", "task-1")

        state = make_task_state("task-1", TaskStatus.COMPLETED, output={"result": 42})
        await adapter._on_task_state_change("task-1", state)

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "task_state"
        assert sent["data"]["task_id"] == "task-1"
        assert sent["data"]["status"] == "completed"

    @pytest.mark.anyio
    async def test_broadcasts_nothing_with_no_subscribers(self):
        adapter = make_adapter()
        state = make_task_state("task-1", TaskStatus.PROCESSING)
        await adapter._on_task_state_change("task-1", state)  # should not raise


class TestSerializeTaskState:
    def test_pending_state(self):
        adapter = make_adapter()
        state = make_task_state("task-1", TaskStatus.PENDING)
        result = adapter._serialize_task_state("task-1", state)
        assert result["task_id"] == "task-1"
        assert result["status"] == "pending"
        assert result["output"] is None
        assert result["error"] is None
        assert result["interrupt"] is None
        assert "timestamp" in result

    def test_completed_state_with_json_output(self):
        adapter = make_adapter()
        state = make_task_state("task-1", TaskStatus.COMPLETED, output={"key": "value"})
        result = adapter._serialize_task_state("task-1", state)
        assert result["status"] == "completed"
        assert result["output"] == {"key": "value"}

    def test_completed_state_with_non_serializable_output(self):
        adapter = make_adapter()
        state = make_task_state("task-1", TaskStatus.COMPLETED, output=object())
        result = adapter._serialize_task_state("task-1", state)
        assert result["output"] is None

    def test_failed_state_with_error(self):
        adapter = make_adapter()
        state = make_task_state("task-1", TaskStatus.FAILED, error=ValueError("oops"))
        result = adapter._serialize_task_state("task-1", state)
        assert result["status"] == "failed"
        assert "oops" in result["error"]

    def test_interrupted_state_with_interrupt(self):
        adapter = make_adapter()
        interrupt = InterruptState(job_id="job-1", phase="before", message="confirm?")
        state = make_task_state("task-1", TaskStatus.INTERRUPTED, interrupt=interrupt)
        result = adapter._serialize_task_state("task-1", state)
        assert result["status"] == "interrupted"
        assert result["interrupt"]["job_id"] == "job-1"
        assert result["interrupt"]["phase"] == "before"
        assert result["interrupt"]["message"] == "confirm?"


# ============================
# WebSocket message handlers
# ============================

class TestHandleWsMessage:
    @pytest.mark.anyio
    async def test_invalid_json_sends_error(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)
        await adapter._handle_ws_message("client-1", "not-json{{{")
        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "INVALID_REQUEST"

    @pytest.mark.anyio
    async def test_unknown_message_type_sends_error(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)
        await adapter._handle_ws_message("client-1", json.dumps({"type": "unknown_op"}))
        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"


class TestWsRunWorkflow:
    @pytest.mark.anyio
    async def test_run_workflow_sends_workflow_started(self):
        state = make_task_state("task-99", TaskStatus.PENDING)
        controller = make_controller(task_state=state)
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        data = {"workflow_id": "__default__", "subscribe_task": False}
        await adapter._ws_run_workflow("client-1", "msg-1", data)

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "workflow_started"
        assert sent["id"] == "msg-1"
        assert sent["data"]["task_id"] == "task-99"

    @pytest.mark.anyio
    async def test_run_workflow_subscribes_when_requested(self):
        state = make_task_state("task-99", TaskStatus.PENDING)
        controller = make_controller(task_state=state)
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        data = {"workflow_id": "__default__", "subscribe_task": True}
        await adapter._ws_run_workflow("client-1", "msg-1", data)

        assert "client-1" in adapter.websocket_manager._task_subscriptions.get("task-99", set())

    @pytest.mark.anyio
    async def test_run_workflow_not_found_sends_error(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        data = {"workflow_id": "nonexistent"}
        await adapter._ws_run_workflow("client-1", "msg-1", data)

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "WORKFLOW_NOT_FOUND"


class TestWsSubscribeTask:
    @pytest.mark.anyio
    async def test_subscribe_sends_task_subscribed(self):
        state = make_task_state("task-1", TaskStatus.PROCESSING)
        controller = make_controller(task_state=state)
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_subscribe_task("client-1", "msg-1", {"task_id": "task-1"})

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "task_subscribed"
        assert sent["data"]["task_id"] == "task-1"

    @pytest.mark.anyio
    async def test_subscribe_missing_task_id_sends_error(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_subscribe_task("client-1", "msg-1", {})

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "INVALID_REQUEST"

    @pytest.mark.anyio
    async def test_subscribe_unknown_task_sends_error(self):
        controller = make_controller()
        controller.get_task_state.return_value = None
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_subscribe_task("client-1", "msg-1", {"task_id": "no-such-task"})

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "TASK_NOT_FOUND"


class TestWsUnsubscribeTask:
    @pytest.mark.anyio
    async def test_unsubscribe_sends_task_unsubscribed(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)
        adapter.websocket_manager.subscribe_to_task("client-1", "task-1")

        await adapter._ws_unsubscribe_task("client-1", "msg-1", {"task_id": "task-1"})

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "task_unsubscribed"
        assert sent["data"]["task_id"] == "task-1"

    @pytest.mark.anyio
    async def test_unsubscribe_missing_task_id_sends_error(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_unsubscribe_task("client-1", "msg-1", {})

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "INVALID_REQUEST"


class TestWsResumeTask:
    @pytest.mark.anyio
    async def test_resume_sends_task_resumed(self):
        state = make_task_state("task-1", TaskStatus.PROCESSING)
        controller = make_controller(task_state=state)
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_resume_task(
            "client-1", "msg-1",
            {"task_id": "task-1", "job_id": "job-1", "answer": "yes"}
        )

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "task_resumed"
        assert sent["data"]["task_id"] == "task-1"

    @pytest.mark.anyio
    async def test_resume_missing_fields_sends_error(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_resume_task("client-1", "msg-1", {"task_id": "task-1"})

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "INVALID_REQUEST"

    @pytest.mark.anyio
    async def test_resume_not_interrupted_sends_error(self):
        controller = make_controller()
        controller.resume_workflow.side_effect = ValueError("task is not in interrupted state")
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_resume_task(
            "client-1", "msg-1",
            {"task_id": "task-1", "job_id": "job-1"}
        )

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "TASK_NOT_INTERRUPTED"

    @pytest.mark.anyio
    async def test_resume_job_id_mismatch_sends_error(self):
        controller = make_controller()
        controller.resume_workflow.side_effect = ValueError("Job ID mismatch")
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_resume_task(
            "client-1", "msg-1",
            {"task_id": "task-1", "job_id": "wrong-job"}
        )

        sent = ws.send_json.call_args[0][0]
        assert sent["data"]["code"] == "JOB_ID_MISMATCH"


class TestWsGetTask:
    @pytest.mark.anyio
    async def test_get_task_sends_task_state(self):
        state = make_task_state("task-1", TaskStatus.COMPLETED, output={"x": 1})
        controller = make_controller(task_state=state)
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_get_task("client-1", "msg-1", {"task_id": "task-1"})

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "task_state"
        assert sent["id"] == "msg-1"
        assert sent["data"]["task_id"] == "task-1"

    @pytest.mark.anyio
    async def test_get_task_missing_task_id_sends_error(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_get_task("client-1", "msg-1", {})

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["data"]["code"] == "INVALID_REQUEST"

    @pytest.mark.anyio
    async def test_get_task_not_found_sends_error(self):
        controller = make_controller()
        controller.get_task_state.return_value = None
        adapter = make_adapter(controller=controller)
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_get_task("client-1", "msg-1", {"task_id": "ghost"})

        sent = ws.send_json.call_args[0][0]
        assert sent["data"]["code"] == "TASK_NOT_FOUND"


class TestWsPing:
    @pytest.mark.anyio
    async def test_ping_sends_pong(self):
        adapter = make_adapter()
        ws = make_websocket()
        await adapter.websocket_manager.connect("client-1", ws)

        await adapter._ws_ping("client-1", "msg-1", {})

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "pong"
        assert sent["id"] == "msg-1"
        assert "timestamp" in sent["data"]
